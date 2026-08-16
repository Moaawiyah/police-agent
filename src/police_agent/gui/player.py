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

from police_agent.gui import live_events, live_restart
from police_agent.gui.game_mode import mode_and_model
from police_agent.gui.live_controls import LiveControls
from police_agent.gui.window import PeerWindow
from police_agent.sdk import GameControls
from police_agent.shared.version import CODE_VERSION

DRAIN_INTERVAL_MS = 100
CLOCK_INTERVAL_MS = 1000
QUIT_GRACE_MS = 400
DEFAULT_STEP_SECONDS = 0.0


class LivePeerApp:
    """Runs the police agent in a thread and shows what it is doing."""

    def __init__(self, agent, controls=None) -> None:
        """Build the window for `agent` and open its server/tunnel immediately,
        so the opponent can reach us as soon as the window is up. Start still
        gates the actual handshake/play -- only the listening moves earlier."""
        self._agent = agent
        self._controls = controls or GameControls()
        agent.listener = self._on_event  # read when the runtime is built, on Start
        agent.controls = self._controls
        agent.connect()
        self._events: queue.Queue = queue.Queue()
        self._summaries: list[dict] = []
        self._started_at: float | None = None
        self._in_progress = False  # whether a worker thread currently owns _agent
        self._title = f"POLICE - {agent.config.get('game.group_id', 'unnamed')} - port {agent.port}"
        self._window = PeerWindow(
            self._title,
            agent.config.require("board.size"),
            float(agent.config.get("gui.step_seconds", DEFAULT_STEP_SECONDS)),
        )
        self._describe_verbal_layer()
        self._bar = LiveControls(self._window.root, self)

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
        """Begin the handshake and play. The server/tunnel are already open;
        this is what starts actually talking to the opponent."""
        self._bar.mark_started()
        self._in_progress = True
        self._started_at = time.monotonic()
        total = self._agent.config.get("game.num_games", 1)
        self._window.set_label("game", f"1 / {total}")
        self._window.set_turn(False, "STARTING - negotiating terms...")
        threading.Thread(target=self._worker, daemon=True, name="police-runtime").start()
        self._window.root.after(
            CLOCK_INTERVAL_MS,
            lambda: live_events.tick_clock(self, self._title, CLOCK_INTERVAL_MS),
        )

    def pause(self) -> None:
        """Hold this peer. The thief's watchdog keeps running -- see peer/controls."""
        self._controls.pause()
        self._window.set_turn(False, "PAUSED - the thief's clock is still running")

    def play(self) -> None:
        """Resume a paused match."""
        self._controls.play()
        self._window.set_turn(False, "RESUMED")

    def stop(self) -> None:
        """Abandon the running sub-game."""
        self._controls.stop()
        self._window.set_turn(False, "STOPPING - abandoning this sub-game...")

    def quit(self) -> None:
        """Close down cleanly, giving a running game a moment to notice the stop."""
        self._controls.stop()
        self._window.set_turn(False, "QUITTING...")
        self._window.root.after(QUIT_GRACE_MS, self._window.root.destroy)

    def restart(self) -> None:
        """Request a fresh sub-game -- mid-game or after one has ended."""
        live_restart.restart(self)

    def toggle_bidirectional(self) -> None:
        """Opt in to the bidirectional restart/quit control channel."""
        live_restart.toggle_bidirectional(self)

    def _worker(self) -> None:
        live_events.worker(self)

    def _on_event(self, event: dict) -> None:
        """Called on the game thread; see `live_events.on_event` for the pipeline."""
        live_events.on_event(self, event)

    def run(self) -> list[dict]:
        """Show the window and block until it closes; return every sub-game
        played, in order -- the whole series, not just the last one, so a
        caller can report it exactly the way the headless series path does."""
        self._window.set_turn(False, "READY - press Start")
        self._window.root.after(
            DRAIN_INTERVAL_MS, lambda: live_events.drain(self, DRAIN_INTERVAL_MS)
        )
        self._window.root.mainloop()
        return self._summaries
