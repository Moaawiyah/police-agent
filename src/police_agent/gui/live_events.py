"""The event pump for `LivePeerApp`, split out of player.py to keep both
files within the 150-line rule.

Takes the app rather than embedding this in `LivePeerApp` for the same reason
`live_restart.py` takes it: the worker thread, the queue it feeds, and the Tk
polling loop that drains it are one mechanism, testable on their own without
a real Tk root.
"""

import time

from police_agent.exceptions import RestartRequested
from police_agent.gui import live_restart
from police_agent.gui.live_apply import apply_event


def worker(app) -> None:
    try:
        app._summaries = app._agent.play_series()
    except RestartRequested:
        # agent.play() has already unwound on this thread -- never two
        # runtimes racing. Dispatched via `after`: Tk is not thread-safe.
        app._window.root.after(0, lambda: live_restart.rebuild_and_start(app))
    except Exception as exc:  # noqa: BLE001 - a dead thread would show nothing
        # The window is the only place a background failure can surface. A
        # traceback into a daemon thread's stderr is invisible to whoever is
        # watching the board, and they are the one who has to react to it.
        app._events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})


def on_event(app, event: dict) -> None:
    """Called on the game thread: hand the event over, then pace the match.

    The sleep is here rather than in the drain loop because it must slow the
    *game*, not the drawing -- a delay applied on the Tk side would let the
    runtime race ahead and the board would jump.
    """
    app._events.put(event)
    if event["type"] == "moved":
        time.sleep(max(0.0, app._window.speed.get()))


def drain(app, interval_ms: int) -> None:
    while not app._events.empty():
        event = app._events.get_nowait()
        apply_event(app._window, event)
        if event["type"] in ("game_over", "error"):
            app._started_at = None  # the clock stops with the game
            app._in_progress = False
            app._bar.mark_finished()
    app._window.root.after(interval_ms, lambda: drain(app, interval_ms))


def tick_clock(app, title: str, interval_ms: int) -> None:
    if app._started_at is not None:
        elapsed = int(time.monotonic() - app._started_at)
        app._window.root.title(f"{title} | {elapsed // 60:02d}:{elapsed % 60:02d}")
    app._window.root.after(interval_ms, lambda: tick_clock(app, title, interval_ms))
