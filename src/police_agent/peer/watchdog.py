"""Watchdog: an independent liveness monitor for the turn loop (spec ch. 8.4).

Distinct from DeadlineTracker (mcp_client.py's per-call timeouts, already
bounding every network round trip): this watches the LOOP's overall
progress via a heartbeat, on its own thread, catching a hang OUTSIDE any one
bounded call -- a wedge inside apply_incoming/TurnHandler.process/
brain.decide/a hint call whose own timeout failed.

What this CAN do: notice, from a second thread, that beat() hasn't been
called in timeout_sec, and ask the loop to stop at its next natural
checkpoint -- the same controls.stopped check that already ends a
GUI-initiated Stop cleanly. What this CANNOT do: forcibly interrupt a main
thread wedged in a tight non-yielding loop or a blocking call that never
returns control to Python -- no background thread can preempt that under
the GIL; only an external process kill can. This rescues the realistic case
(an unbounded wait, a slow-but-eventually-returning call), not a truly dead
interpreter.
"""

import threading
import time
from collections.abc import Callable

from police_agent.peer.controls import GameControls

# Last-resort fallback only, for a Watchdog built without a config (see
# tests) or against a config missing the agreed network.watchdog_timeout_seconds
# entirely. ch. 8.4.2's illustrative snippet uses this same number, but
# Appendix Vav's own preamble is explicit that a value is authoritative only
# in its tables (Table 19 item 7 = 60s) -- never in body-text example code.
DEFAULT_TIMEOUT_SEC = 180.0
WATCHDOG_POLL_SECONDS = 5.0
WATCHDOG_POLL_SECONDS = 5.0


class Watchdog:
    """Background heartbeat monitor; trips by calling controls.stop()."""

    def __init__(
        self,
        controls: GameControls,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        poll_sec: float = WATCHDOG_POLL_SECONDS,
        clock=time.monotonic,
        on_trip: Callable[[str], None] | None = None,
    ) -> None:
        """Watch `controls` for a stalled loop; call `on_trip` and stop it past `timeout_sec`."""
        self._controls = controls
        self._timeout_sec = timeout_sec
        self._poll_sec = poll_sec
        self._clock = clock
        self._on_trip = on_trip
        self._lock = threading.Lock()
        self._last_beat = clock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.tripped = False

    @property
    def timeout_sec(self) -> float:
        """How long the loop may go without a heartbeat before this trips."""
        return self._timeout_sec

    @classmethod
    def from_config(cls, config, controls: GameControls, on_trip=None) -> "Watchdog":
        """Defaults to the AGREED `network.watchdog_timeout_seconds` (Table 19
        item 7, "time until deadlock -> Watchdog intervention", 60s, shared
        and negotiable) -- ch. 8.4.2 names this exact field as the loop-
        liveness threshold, not `response_timeout_sec`/item 6's per-call
        deadline. `[reliability]` in the private TOML can still override it
        locally, for a peer that wants its OWN loop watched more or less
        strictly than the shared default; that override never touches the
        agreed file and the opponent never sees it."""
        timeout = float(
            config.get("reliability.loop_watchdog_timeout_seconds")
            or config.get("network.watchdog_timeout_seconds")
            or DEFAULT_TIMEOUT_SEC
        )
        return cls(controls, timeout_sec=timeout, on_trip=on_trip)

    def beat(self) -> None:
        """Record that the loop reached this point, just now."""
        with self._lock:
            self._last_beat = self._clock()

    def start(self) -> None:
        """Begin monitoring. Resets the clock here, not in __init__: the
        object is built before negotiate() runs, which can legitimately take
        up to connect_timeout -- counting from construction would eat into
        the loop's own budget before the loop has run once."""
        with self._lock:
            self._last_beat = self._clock()
        self._thread = threading.Thread(target=self._run, daemon=True, name="watchdog")
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitor thread, joined with a bounded wait (same idiom as
        infra/tunnel.py's NgrokTunnel.close()) so a watchdog whose sub-game
        already ended cannot trip a moment later against a *different*,
        freshly started sub-game sharing the same GameControls."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_sec)

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._poll_sec):
            if self._controls.paused:
                # A human-held pause is not a hang -- controls.py already
                # accepts that risk (the OPPONENT's watchdog may time out
                # instead); this one must not race a different reason.
                self.beat()
                continue
            with self._lock:
                elapsed = self._clock() - self._last_beat
            if elapsed > self._timeout_sec:
                self._trip(elapsed)
                return

    def _trip(self, elapsed: float) -> None:
        self.tripped = True
        reason = (
            f"watchdog: main loop unresponsive for {elapsed:.0f}s (limit {self._timeout_sec:.0f}s)"
        )
        if self._on_trip is not None:
            self._on_trip(reason)
        self._controls.stop()
