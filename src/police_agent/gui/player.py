"""LivePeerApp: this agent playing a real match, mirrored in a window.

The game runs on a worker thread and Tk owns the main one, so the two never
touch the same object: the runtime posts events into a queue and the main loop
drains it every hundred milliseconds. That is also why every event carries its
own view -- see `peer/view.py`. A GUI that reached into the runtime for the
board would be reading it while the worker was still writing.

The window holds no game logic. It presses Start, then renders what arrives.
"""

import queue
import threading
import time

from police_agent.gui.game_mode import mode_and_model
from police_agent.gui.live_apply import apply_event
from police_agent.gui.live_controls import LiveControls
from police_agent.gui.window import PeerWindow
from police_agent.peer.controls import GameControls
from police_agent.shared.version import CODE_VERSION

DRAIN_INTERVAL_MS = 100
CLOCK_INTERVAL_MS = 1000
QUIT_GRACE_MS = 400
DEFAULT_STEP_SECONDS = 0.0


class LivePeerApp:
    """Runs the police agent in a thread and shows what it is doing."""

    def __init__(self, agent, controls=None) -> None:
        self._agent = agent
        self._controls = controls or GameControls()
        agent.listener = self._on_event  # read when the runtime is built, on Start
        agent.controls = self._controls
        self._events: queue.Queue = queue.Queue()
        self._summary: dict | None = None
        self._started_at: float | None = None
        self._title = self._build_title()
        self._window = PeerWindow(
            self._title,
            agent.config.require("board.size"),
            float(agent.config.get("gui.step_seconds", DEFAULT_STEP_SECONDS)),
        )
        self._describe_verbal_layer()
        self._bar = LiveControls(self._window.root, self)

    def _build_title(self) -> str:
        group = self._agent.config.get("game.group_id", "unnamed")
        return f"POLICE - {group} - port {self._agent.port}"

    def _describe_verbal_layer(self) -> None:
        mode, model = mode_and_model(self._agent.config)
        self._window.add_menu(
            {
                "code_version": CODE_VERSION,
                "role": "police",
                "verbal_mode": mode,
                "model": model,
                "board": self._agent.config.require("board.size"),
                "opponent": self._agent.opponent_url,
            }
        )
        self._window.set_label("mode", mode)
        self._window.set_label("model", model)

    def start(self) -> None:
        """Open the link and play. Nothing has touched the network before this."""
        self._bar.mark_started()
        self._started_at = time.monotonic()
        self._window.set_turn(False, "STARTING - negotiating terms...")
        threading.Thread(target=self._worker, daemon=True, name="police-runtime").start()
        self._window.root.after(CLOCK_INTERVAL_MS, self._tick_clock)

    def pause(self) -> None:
        """Hold this peer. The thief's watchdog keeps running -- see peer/controls."""
        self._controls.pause()
        self._window.set_turn(False, "PAUSED - the thief's clock is still running")

    def play(self) -> None:
        self._controls.play()
        self._window.set_turn(False, "RESUMED")

    def stop(self) -> None:
        self._controls.stop()
        self._window.set_turn(False, "STOPPING - abandoning this sub-game...")

    def quit(self) -> None:
        """Close down cleanly, giving a running game a moment to notice the stop."""
        self._controls.stop()
        self._window.set_turn(False, "QUITTING...")
        self._window.root.after(QUIT_GRACE_MS, self._window.root.destroy)

    def _worker(self) -> None:
        try:
            self._summary = self._agent.play()
        except Exception as exc:  # noqa: BLE001 - a dead thread would show nothing
            # The window is the only place a background failure can surface. A
            # traceback into a daemon thread's stderr is invisible to whoever is
            # watching the board, and they are the one who has to react to it.
            self._events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

    def _on_event(self, event: dict) -> None:
        """Called on the game thread: hand the event over, then pace the match.

        The sleep is here rather than in the drain loop because it must slow the
        *game*, not the drawing -- a delay applied on the Tk side would let the
        runtime race ahead and the board would jump.
        """
        self._events.put(event)
        if event["type"] == "moved":
            time.sleep(max(0.0, self._window.speed.get()))

    def _drain(self) -> None:
        while not self._events.empty():
            event = self._events.get_nowait()
            apply_event(self._window, event)
            if event["type"] in ("game_over", "error"):
                self._started_at = None  # the clock stops with the game
                self._bar.mark_finished()
        self._window.root.after(DRAIN_INTERVAL_MS, self._drain)

    def _tick_clock(self) -> None:
        if self._started_at is not None:
            elapsed = int(time.monotonic() - self._started_at)
            self._window.root.title(f"{self._title} | {elapsed // 60:02d}:{elapsed % 60:02d}")
        self._window.root.after(CLOCK_INTERVAL_MS, self._tick_clock)

    def run(self) -> dict | None:
        """Show the window and block until it closes; return the summary if any."""
        self._window.set_turn(False, "READY - press Start")
        self._window.root.after(DRAIN_INTERVAL_MS, self._drain)
        self._window.root.mainloop()
        return self._summary
