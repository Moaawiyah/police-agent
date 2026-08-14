"""`game_over`'s own detail: audit wording, reliability, and the sub-game
panel, split out of test_live_apply.py to keep both files under the
project's line budget.
"""

from tests.gui.test_live_apply import SUMMARY, VIEW, apply


def test_game_over_reports_the_result_and_what_the_audit_proved():
    window = apply({"type": "game_over", "summary": SUMMARY, "view": VIEW})

    assert window.banner == (False, "GAME OVER: capture - winner POLICE")
    assert "Audit PASSED, 4 steps" in window.labels["status"]
    assert window.labels["reliability"] == "0.81 - believable"


def test_sub_game_over_reports_progress_rather_than_ending_the_session():
    """Distinct from `game_over`: more sub-games may still follow, so the
    wording must not read as the whole series being finished."""
    window = apply({"type": "sub_game_over", "summary": SUMMARY, "sub_game_number": 2, "view": VIEW})

    assert window.banner == (False, "SUB-GAME 2 DONE: capture - winner police")
    assert "next sub-game" in window.labels["status"]
    assert window.labels["game"] == "2 complete"


def test_game_over_marks_the_sub_game_panel_with_the_final_agreed_count():
    """The number both peers agreed on: `sub_game_number` here is `len(summaries)`
    from `play_series`, which only reaches this event once the whole signed-term
    `num_games` count has actually been played (see `sdk/agent.py::play_series`)."""
    window = apply({"type": "game_over", "summary": SUMMARY, "sub_game_number": 3, "view": VIEW})

    assert window.labels["game"] == "3 / 3 complete"


def test_a_drawn_game_names_nobody_rather_than_crashing_on_a_null_winner():
    summary = {**SUMMARY, "result": "timeout", "winner": None}

    window = apply({"type": "game_over", "summary": summary, "view": VIEW})

    assert window.banner == (False, "GAME OVER: timeout - winner NOBODY")


def test_a_skipped_audit_is_not_reported_as_a_pass():
    """Nothing was proven either way, and saying `PASSED` would claim it was."""
    summary = {**SUMMARY, "audit": {"passed": False, "verified_steps": 0, "skipped": True}}

    window = apply({"type": "game_over", "summary": summary, "view": VIEW})

    assert "not exchanged" in window.labels["status"]
    assert "PASSED" not in window.labels["status"]


def test_a_thief_that_lied_its_way_through_is_reported_as_disbelieved():
    summary = {**SUMMARY, "opponent_reliability": 0.2}

    window = apply({"type": "game_over", "summary": summary, "view": VIEW})

    assert "disbelief" in window.labels["reliability"]
