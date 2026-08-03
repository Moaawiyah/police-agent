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
"""

import threading

PAUSE_POLL_SECONDS = 0.2


class GameControls:
    """Thread-safe switches shared by a front end and the runtime it drives."""

    def __init__(self) -> None:
        self._resume = threading.Event()
        self._resume.set()  # running unless something pauses it
        self._stop = threading.Event()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

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
