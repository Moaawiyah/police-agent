"""Runtime events becoming what the live window shows."""

from police_agent.domain.rules import CAPTURE
from police_agent.gui.live_apply import apply_event
from police_agent.strategy.decision import Decision
from tests.gui.fake_window import FakeWindow

VIEW = {
    "role": "police",
    "step": 4,
    "position": (1, 2),
    "visited": {(0, 0), (1, 2)},
    "barriers": set(),
    "belief": [[0.5, 0.5], [0.0, 0.0]],
    "barriers_used": 1,
    "barriers_max": 14,
}

AUDIT = {"passed": True, "verified_steps": 4, "failed_steps": []}
SUMMARY = {
    "result": CAPTURE,
    "winner": "police",
    "steps": 4,
    "duration_seconds": 12.5,
    "audit": AUDIT,
    "opponent_reliability": 0.81,
}


def apply(event: dict) -> FakeWindow:
    window = FakeWindow()
    apply_event(window, event)
    return window


def test_a_view_is_rendered_whatever_the_event_says():
    window = apply({"type": "incoming", "step": 4, "hint": "catch me", "view": VIEW})

    assert window.views == [VIEW]
    assert window.labels["barriers"] == "1 / 14"


def test_an_arriving_turn_turns_the_banner_green():
    """The message is the turn token: receiving one is what makes it my move."""
    window = apply({"type": "incoming", "step": 4, "hint": "catch me", "view": VIEW})

    assert window.banner == (True, None)
    assert window.labels["hint_in"] == "step 4: catch me"


def test_a_silent_opponent_is_shown_as_silent_not_as_blank():
    window = apply({"type": "incoming", "step": 4, "hint": "", "view": VIEW})

    assert window.labels["hint_in"] == "step 4: (silent)"


def test_the_handshake_reports_the_peer_it_agreed_with():
    window = apply({"type": "negotiated", "peer": {"group_id": "thief-team"}, "view": VIEW})

    assert "thief-team" in window.labels["hint_in"]
    assert "SHA-256" in window.labels["status"]
    assert window.banner == (False, None)  # the thief opens, so we wait


def test_a_handshake_with_an_unnamed_peer_still_renders():
    window = apply({"type": "negotiated", "view": VIEW})

    assert "unknown" in window.labels["hint_in"]


def test_my_move_shows_the_reason_and_only_the_head_of_the_commit():
    """The commitment is what the opponent may not see until the audit, so a
    screenshot of this window must not leak more than the wire did."""
    decision = Decision(None, "closing on the strongest scent")
    window = apply(
        {
            "type": "moved",
            "decision": decision,
            "commit": "a" * 64,
            "hint": "I can smell you",
            "view": VIEW,
        }
    )

    assert window.labels["verdict"] == "closing on the strongest scent"
    assert window.labels["hint_out"] == "step 4: I can smell you"
    assert window.labels["commit"] == "a" * 32 + "..."
    assert "a" * 64 not in window.labels["commit"]
    assert window.banner == (False, None)  # the turn has been handed over


def test_a_replayed_turn_says_so_without_claiming_a_move():
    window = apply({"type": "replay_ignored", "step": 2, "view": VIEW})

    assert "ignored" in window.labels["status"]
    assert window.banner is None  # nothing about whose turn it is has changed


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


def test_an_error_reaches_the_window_instead_of_dying_in_a_daemon_thread():
    """The worker's stderr is invisible to whoever is watching the board, and
    they are the one who has to react to it."""
    window = apply({"type": "error", "message": "TransportError: opponent unreachable"})

    assert window.banner == (False, "ERROR - see status")
    assert window.labels["status"] == "TransportError: opponent unreachable"
    assert window.views == []  # an error carries no view to draw


def test_an_unknown_event_renders_its_view_and_changes_nothing_else():
    """Adding an event to the runtime must not crash a window built before it."""
    window = apply({"type": "something_new", "view": VIEW})

    assert window.views == [VIEW]
    assert window.banner is None
