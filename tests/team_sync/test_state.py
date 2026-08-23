"""role_for_subgame's alternation table, and the state machine's legal moves."""

import pytest

from police_agent.team_sync.state import SeriesSyncState, SeriesSyncStatus, role_for_subgame
from police_agent.team_sync.state_transitions import can_transition


@pytest.mark.parametrize(
    ("sub_game_number", "expected"),
    [(1, "police"), (2, "thief"), (3, "police"), (4, "thief"), (5, "police"), (6, "thief")],
)
def test_role_for_subgame_alternates_starting_with_police(sub_game_number, expected):
    assert role_for_subgame(sub_game_number) == expected


def test_idle_can_move_to_ready():
    assert can_transition(SeriesSyncState.IDLE, SeriesSyncState.READY) is True


def test_idle_cannot_jump_straight_to_settled():
    assert can_transition(SeriesSyncState.IDLE, SeriesSyncState.SETTLED) is False


def test_series_complete_and_error_are_terminal():
    assert can_transition(SeriesSyncState.SERIES_COMPLETE, SeriesSyncState.READY) is False
    assert can_transition(SeriesSyncState.ERROR, SeriesSyncState.READY) is False


def test_advance_follows_the_legal_path_from_ready_to_settled():
    status = SeriesSyncStatus(series_id="s1", state=SeriesSyncState.READY)

    status = status.advance(SeriesSyncState.NEGOTIATING)
    status = status.advance(SeriesSyncState.PLAYING)
    status = status.advance(SeriesSyncState.AUDITING)
    status = status.advance(SeriesSyncState.SETTLED)

    assert status.state == SeriesSyncState.SETTLED
    assert status.updated_at  # stamped on every legal move


def test_advance_refuses_an_illegal_jump():
    status = SeriesSyncStatus(series_id="s1", state=SeriesSyncState.IDLE)

    with pytest.raises(ValueError, match="illegal team_sync transition"):
        status.advance(SeriesSyncState.SERIES_COMPLETE)


def test_advance_can_move_the_sub_game_number_forward():
    status = SeriesSyncStatus(series_id="s1", sub_game_number=1, state=SeriesSyncState.SETTLED)

    status = status.advance(SeriesSyncState.READY, sub_game_number=2)

    assert status.sub_game_number == 2


def test_to_dict_and_from_dict_round_trip():
    status = SeriesSyncStatus(series_id="s1", sub_game_number=3, state=SeriesSyncState.PLAYING)

    rebuilt = SeriesSyncStatus.from_dict(status.to_dict())

    assert rebuilt == status
