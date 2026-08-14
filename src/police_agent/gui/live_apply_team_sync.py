"""Rendering team_sync's own status events.

Split from `live_apply.py` to keep it within budget, mirroring the existing
`replay.py`/`replay_actions.py` split-for-budget convention. These events
cover the even sub-games this process never plays itself -- no
`PoliceRuntime` event exists for "the sibling Thief process is playing sub-
game 4 right now", so `scheduler.py` emits one of these instead.

Deliberately never renders the words "GAME OVER": that banner belongs only
to the real, once-per-series end, which `live_apply.py`'s existing
`_apply_game_over` already owns via the relabelled `sub_game_over`/
`game_over` events -- see `sdk/series.py::series_listener`, reused
unchanged by `scheduler.py` for Police's own sub-games.
"""

_LABELS = {
    "WAITING": "WAITING FOR SUBGAME {n}",
    "READY": "READY FOR SUBGAME {n}",
    "PLAYING": "PLAYING SUBGAME {n}",
    "AUDITING": "AUDITING SUBGAME {n}",
    "SETTLED": "SUBGAME {n} SETTLED",
    "SERIES_COMPLETE": "SERIES COMPLETE",
    "SYNC_ERROR": "SYNC ERROR",
    "waiting_for_sibling": "WAITING FOR THIEF SUBGAME {n}",
    "ready_for_subgame": "READY FOR SUBGAME {n}",
    "subgame_settled": "SUBGAME {n} RECEIVED AND SETTLED",
    "building_final_report": "BUILDING FINAL REPORT...",
    "email_sent": "EMAIL SENT",
    "series_complete": "SERIES COMPLETE",
}


def apply_team_sync_event(window, event: dict) -> None:
    """Render one `{"type": "team_sync", ...}` status event."""
    status = event.get("state") or event.get("status", "")
    text = _LABELS.get(status, status.upper()).format(n=event.get("sub_game_number", "?"))
    window.set_turn(False, text)
    window.set_label("status", text)
