"""Rendering team_sync's own status events -- the even sub-games this
process never plays itself.
"""

from police_agent.gui.live_apply import apply_event
from tests.gui.fake_window import FakeWindow


def test_waiting_for_the_sibling_names_the_subgame_number():
    window = FakeWindow()

    apply_event(
        window, {"type": "team_sync", "status": "waiting_for_sibling", "sub_game_number": 4}
    )

    assert window.banner == (False, "WAITING FOR THIEF SUBGAME 4")


def test_a_settled_import_is_reported_by_subgame_number():
    window = FakeWindow()

    apply_event(window, {"type": "team_sync", "status": "subgame_settled", "sub_game_number": 4})

    assert "SUBGAME 4 RECEIVED AND SETTLED" in window.labels["status"]


def test_an_unmapped_status_falls_back_to_its_own_uppercased_name():
    window = FakeWindow()

    apply_event(window, {"type": "team_sync", "status": "email_sent", "sub_game_number": 6})

    assert window.labels["status"] == "EMAIL SENT"


def test_team_sync_events_never_render_the_words_game_over():
    window = FakeWindow()

    apply_event(window, {"type": "team_sync", "status": "subgame_settled", "sub_game_number": 2})

    assert "GAME OVER" not in window.labels["status"]
