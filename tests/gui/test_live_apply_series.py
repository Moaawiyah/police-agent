"""The series-level verdict `game_over` shows once `totals` is attached.

Split from test_live_apply.py to keep both files under the project's
150-line rule -- see tests/sdk/test_agent_series.py for the same split.
"""

from police_agent.domain.rules import CAPTURE
from police_agent.gui.live_apply import apply_event
from tests.gui.fake_window import FakeWindow
from tests.gui.test_live_apply import SUMMARY, VIEW


def apply(event: dict) -> FakeWindow:
    window = FakeWindow()
    apply_event(window, event)
    return window


def test_a_series_win_names_the_winning_group_not_a_role():
    """Roles alternate across a series (ch. 9.3.3), so the banner must name
    the group that won, not just repeat "police" the way a single sub-game
    winner does."""
    totals = {"total_score": {"us": 25, "them": 10}, "sub_games_won": {"us": 2, "them": 1}}
    totals["winner_group"] = "us"

    window = apply({"type": "game_over", "summary": SUMMARY, "totals": totals, "view": VIEW})

    assert window.banner == (False, "SERIES COMPLETE - winner us")
    assert "final score" in window.labels["status"]
    assert "25" in window.labels["status"]


def test_a_tied_series_names_no_group():
    totals = {"total_score": {"us": 15, "them": 15}, "sub_games_won": {"us": 1, "them": 1}}
    totals["winner_group"] = None

    window = apply({"type": "game_over", "summary": SUMMARY, "totals": totals, "view": VIEW})

    assert window.banner == (False, "SERIES COMPLETE: TIE")


def test_no_totals_falls_back_to_the_single_game_wording():
    """`play_series` always attaches `totals`, but `_apply_game_over` must not
    crash if a bare `runtime.run()` event ever reaches it without one."""
    summary = {**SUMMARY, "result": CAPTURE, "winner": "police"}

    window = apply({"type": "game_over", "summary": summary, "view": VIEW})

    assert window.banner == (False, "GAME OVER: capture - winner POLICE")
    assert "final score" not in window.labels["status"]
