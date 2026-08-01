"""Tests for OwnGameState: the police peer's private, authoritative-for-itself state."""

import pytest

from police_agent.constants import Direction
from police_agent.domain.actions import barrier, hold, move
from police_agent.domain.own_state import OwnGameState


def police(start=(0, 0), board_size=7):
    return OwnGameState(start=start, board_size=board_size)


class TestSetup:
    def test_starts_on_its_start_cell(self):
        state = police(start=(3, 3))
        assert state.position == (3, 3)
        assert state.unique_cells == 1
        assert state.step_number == 0

    def test_rejects_a_start_cell_off_the_board(self):
        with pytest.raises(ValueError, match="off a 7x7 board"):
            police(start=(7, 0))


class TestMovement:
    def test_move_updates_position_and_visited(self):
        state = police(start=(3, 3))
        assert state.apply_move(move(Direction.N))
        assert state.position == (2, 3)
        assert state.unique_cells == 2

    def test_hold_keeps_position_and_unique_count(self):
        state = police(start=(3, 3))
        assert state.apply_move(hold())
        assert state.position == (3, 3)
        assert state.unique_cells == 1
        assert state.step_number == 1  # the turn still counted

    def test_revisiting_a_cell_does_not_raise_the_unique_count(self):
        state = police(start=(3, 3))
        state.apply_move(move(Direction.N))
        state.apply_move(move(Direction.S))
        assert state.position == (3, 3)
        assert state.unique_cells == 2

    def test_move_off_board_is_rejected_and_changes_nothing(self):
        state = police(start=(0, 0))
        assert not state.apply_move(move(Direction.N))
        assert state.position == (0, 0)
        assert state.step_number == 0

    def test_move_into_a_known_barrier_is_rejected(self):
        state = police(start=(3, 3))
        state.note_barrier((2, 3))
        assert not state.apply_move(move(Direction.N))
        assert state.position == (3, 3)


class TestBarrierPlacement:
    def test_walls_an_adjacent_cell_without_moving(self):
        state = police(start=(3, 3))
        assert state.apply_move(barrier(Direction.N), barriers_max=2)
        assert (2, 3) in state.barriers
        assert state.position == (3, 3)

    def test_can_wall_the_cell_underfoot(self):
        # Specification 3.4 allows the fifth placement: the police's own cell.
        state = police(start=(3, 3))
        assert state.apply_move(barrier(), barriers_max=1)
        assert (3, 3) in state.barriers
        assert state.my_barriers == 1

    def test_quota_is_enforced(self):
        state = police(start=(3, 3))
        assert state.apply_move(barrier(Direction.N), barriers_max=1)
        assert not state.apply_move(barrier(Direction.S), barriers_max=1)
        assert (4, 3) not in state.barriers

    def test_a_zero_quota_blocks_every_placement(self):
        assert not police(start=(3, 3)).apply_move(barrier(Direction.N))

    def test_cannot_wall_off_board_or_an_existing_barrier(self):
        state = police(start=(0, 0))
        assert not state.apply_move(barrier(Direction.N), barriers_max=5)
        assert state.apply_move(barrier(Direction.E), barriers_max=5)
        assert not state.apply_move(barrier(Direction.E), barriers_max=5)

    def test_last_barrier_reports_the_cell_to_declare(self):
        state = police(start=(3, 3))
        state.apply_move(barrier(Direction.W), barriers_max=1)
        assert state.last_barrier() == (3, 2)
        state.apply_move(move(Direction.N))
        assert state.last_barrier() is None


class TestSelfConfinement:
    """Specification 3.4: a greedy barrier can imprison the police that built it."""

    def test_open_board_is_not_confinement(self):
        assert not police(start=(3, 3)).is_confined()

    def test_walling_itself_in_leaves_no_legal_step(self):
        state = police(start=(3, 3))
        for direction in (Direction.N, Direction.S, Direction.E, Direction.W):
            assert state.apply_move(barrier(direction), barriers_max=4)
        assert state.is_confined()

    def test_board_edges_count_towards_confinement(self):
        state = police(start=(0, 0))
        state.note_barrier((0, 1))
        state.note_barrier((1, 0))
        assert state.is_confined()


class TestLog:
    def test_log_records_each_step(self):
        state = police(start=(0, 0))
        state.apply_move(move(Direction.S))
        state.apply_move(barrier(Direction.E), barriers_max=1)
        assert [entry["move"] for entry in state.log] == ["MOVE:S", "BARRIER:E"]
        assert state.log[-1] == {
            "step": 2,
            "position": [1, 0],
            "move": "BARRIER:E",
            "unique_cells": 2,
            "barrier": [1, 1],
        }
