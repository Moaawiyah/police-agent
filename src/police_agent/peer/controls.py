"""GameControls: pause, resume and stop switches for THIS peer's runtime.

The GUI runs the game on a worker thread and its buttons on the main one, so
these are `threading.Event`s rather than plain flags: an ordinary bool written
from Tk and read from the turn loop is a data race, and `Event.wait` is also the
only way to pause without a busy loop.

Pausing is not free and the window says so. There is no referee to hold the game
while this peer thinks: the thief is waiting on its own watchdog, and a pause
long enough to trip it is a technical loss (spec ch. 2.4.2). The control exists
because a demonstration needs it, not because the game tolerates it.

Stopping abandons the sub-game. The runtime returns a result either way, so a
stopped game still produces a summary and still gets audited -- an agent that
simply vanished would be indistinguishable from one that crashed.

Restart, quit and enable extend the same object to the opt-in bidirectional
control channel (`peer/control_link.py`): a session-level signal, never part
of the sealed record, so none of it can influence a score.
"""

import threading

PAUSE_POLL_SECONDS = 0.2


class GameControls:
    """Thread-safe switches shared by a front end and the runtime it drives."""

    def __init__(self) -> None:
        """Running, unpaused, unstopped -- the state a fresh sub-game starts in."""
        self._resume = threading.Event()
        self._resume.set()  # running unless something pauses it
        self._stop = threading.Event()
        self._restart = threading.Event()  # request a fresh sub-game
        self._quit = threading.Event()  # clean quit (also notifies the opponent)
        self._enable = threading.Event()  # opt in to the bidirectional control channel
        self._status_lock = threading.Lock()
        self._status = "READY"

    @property
    def paused(self) -> bool:
        """Whether the runtime is currently held."""
        return not self._resume.is_set()

    @property
    def stopped(self) -> bool:
        """Whether the sub-game has been abandoned."""
        return self._stop.is_set()

    @property
    def restart_requested(self) -> bool:
        """Whether a fresh sub-game has been requested."""
        return self._restart.is_set()

    @property
    def quit_requested(self) -> bool:
        """Whether a clean quit has been requested."""
        return self._quit.is_set()

    @property
    def enable_requested(self) -> bool:
        """Whether this peer opted in to the bidirectional control channel."""
        return self._enable.is_set()

    def pause(self) -> None:
        """Hold the runtime before its next turn."""
        self._resume.clear()

    def play(self) -> None:
        """Release a paused runtime."""
        self._resume.set()

    def stop(self) -> None:
        """Abandon the sub-game.

        Also releases the pause: a runtime blocked in `wait_if_paused` would
        otherwise never reach the check that notices it has been stopped.
        """
        self._stop.set()
        self._resume.set()

    def request_restart(self) -> None:
        """Ask the active turn loop to abandon this sub-game and rebuild a fresh
        one. Also releases any pause, for the same reason `stop` does."""
        self._restart.set()
        self._resume.set()

    def clear_restart(self) -> None:
        """Consume the restart flag once the runtime has acted on it."""
        self._restart.clear()

    def request_quit(self) -> None:
        """Ask the runtime to quit cleanly, notifying the opponent."""
        self._quit.set()
        self._resume.set()

    def request_enable(self) -> None:
        """Opt in to the bidirectional control channel."""
        self._enable.set()

    def set_status(self, status: str) -> None:
        """Record this peer's current status for the control channel to broadcast."""
        with self._status_lock:
            self._status = status

    @property
    def status(self) -> str:
        """This peer's last-recorded status."""
        with self._status_lock:
            return self._status

    def wait_if_paused(self) -> None:
        """Block while paused, returning at once when playing -- or when stopped.

        The stop is checked *before* each wait rather than after, because Pause
        pressed after Stop is a real sequence: the buttons stay live until the
        game-over event has been drained. Waiting first would hold the runtime on
        an event nothing was ever going to set again.
        """
        while not self._stop.is_set():
            if self._resume.wait(timeout=PAUSE_POLL_SECONDS):
                return
