"""Tests for pure board geometry: bounds, orthogonal steps, barriers."""

import pytest

from police_agent.constants import Direction
from police_agent.domain.board import Board


class TestGeometry:
    def test_rejects_non_positive_size(self):
        with pytest.raises(ValueError, match="must be positive"):
            Board(size=0)

    def test_in_bounds(self):
        board = Board(size=7)
        assert board.in_bounds((0, 0))
        assert board.in_bounds((6, 6))
        assert not board.in_bounds((7, 0))
        assert not board.in_bounds((-1, 3))

    def test_distance_is_manhattan(self):
        # Diagonals are illegal, so (0,0)->(2,3) really costs five steps.
        assert Board(size=7).distance((0, 0), (2, 3)) == 5

    def test_step_applies_the_direction(self):
        board = Board(size=7)
        assert board.step((3, 3), Direction.N) == (2, 3)
        assert board.step((3, 3), Direction.S) == (4, 3)
        assert board.step((3, 3), Direction.E) == (3, 4)
        assert board.step((3, 3), Direction.W) == (3, 2)

    def test_step_off_board_returns_none(self):
        board = Board(size=7)
        assert board.step((0, 0), Direction.N) is None
        assert board.step((6, 6), Direction.S) is None


class TestNoDiagonals:
    def test_direction_enum_has_only_four_members(self):
        # The specification fixes the move set; a diagonal must be unrepresentable.
        assert [d.value for d in Direction] == ["N", "S", "E", "W"]

    def test_centre_cell_has_exactly_four_neighbours(self):
        assert len(Board(size=7).neighbors((3, 3))) == 4

    def test_corner_cell_has_two_neighbours(self):
        assert sorted(Board(size=7).neighbors((0, 0))) == [(0, 1), (1, 0)]


class TestBarriers:
    def test_barrier_blocks_a_step(self):
        assert Board(size=7).step((3, 3), Direction.N, barriers={(2, 3)}) is None

    def test_legal_moves_exclude_barriers(self):
        moves = Board(size=7).legal_moves((0, 0), barriers={(0, 1)})
        assert [cell for _, cell in moves] == [(1, 0)]

    def test_barrier_targets_include_the_cell_underfoot(self):
        # Specification 3.4: own cell plus four neighbours = five candidates.
        targets = Board(size=7).barrier_targets((3, 3))
        assert (3, 3) in targets
        assert len(targets) == 5

    def test_barrier_targets_exclude_off_board_and_walled_cells(self):
        targets = Board(size=7).barrier_targets((0, 0), barriers={(0, 1)})
        assert targets == [(0, 0), (1, 0)]

    def test_barrier_targets_exclude_own_cell_when_already_walled(self):
        targets = Board(size=7).barrier_targets((3, 3), barriers={(3, 3)})
        assert (3, 3) not in targets
        assert len(targets) == 4


class TestReachableArea:
    def test_open_board_reaches_every_cell(self):
        assert Board(size=3).reachable_area((0, 0)) == 9

    def test_a_wall_shrinks_the_pocket(self):
        # Sealing both neighbours of the corner strands it alone.
        board = Board(size=7)
        assert board.reachable_area((0, 0), barriers={(0, 1), (1, 0)}) == 1

    def test_limit_stops_the_fill_early(self):
        board = Board(size=7)
        assert board.reachable_area((3, 3), limit=5) == 5


class TestShortestPathLength:
    def test_same_cell_is_zero(self):
        assert Board(size=7).shortest_path_length((3, 3), (3, 3)) == 0

    def test_matches_manhattan_on_an_open_board(self):
        board = Board(size=7)
        assert board.shortest_path_length((0, 0), (2, 3)) == 5

    def test_a_wall_can_lengthen_the_real_path(self):
        # Manhattan distance stays 2; the real path must detour around the wall.
        board = Board(size=7)
        assert board.shortest_path_length((0, 0), (0, 2), barriers={(0, 1)}) == 4

    def test_none_when_the_goal_is_sealed_off(self):
        board = Board(size=3)
        assert board.shortest_path_length((0, 0), (2, 2), barriers={(0, 1), (1, 0)}) is None
