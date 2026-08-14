"""Restart and the bidirectional control channel, split out of player.py to
keep both files within the 150-line rule.

Takes the app rather than embedding this in `LivePeerApp` for the same reason
`live_apply.py` takes the window: what a restart does does not depend on how
the app was started, and keeping it here makes the mid-game/post-game split
testable without a real Tk root.
"""

from police_agent.sdk import GameControls


def restart(app) -> None:
    """Restart the match: mid-game, ask the running turn loop to abandon it
    through the control channel (`peer/control_link.py`), so the worker
    thread unwinds cleanly by itself before anything rebuilds. Once a game
    has already ended there is no loop left to notice a request, so rebuild
    directly instead -- both paths end at `rebuild_and_start`.
    """
    if app._in_progress:
        app._controls.request_restart()
        app._window.set_label("status", "restart requested...")
        return
    rebuild_and_start(app)


def toggle_bidirectional(app) -> None:
    """Opt in to the bidirectional control channel (status/restart/quit).

    Restarting always works for this peer alone; this is what lets that
    restart also carry to the opponent -- the channel only activates once
    both sides have checked it.
    """
    app._controls.request_enable()


def rebuild_and_start(app) -> None:
    """Reset the whole attempt and wait for the next Start click.

    A restart is a fresh six-subgame attempt, not an automatic continuation.
    The worker/coordinator is only recreated when the user presses Start.
    """
    app._in_progress = False
    app._started_at = None
    app._agent.restart()
    app._agent._team_sync_fresh_start = True
    app._controls = GameControls()
    if app._bar.bidi_var.get():
        app._controls.request_enable()
    app._agent.controls = app._controls
    app._summaries = []
    events = getattr(app, "_events", None)
    if events is not None:
        while not events.empty():
            events.get_nowait()
    if hasattr(app._bar, "mark_ready"):
        app._bar.mark_ready()
    app._window.set_turn(False, "READY - press Start")
    app._window.set_label("status", "SERIES RESET - press Start")
