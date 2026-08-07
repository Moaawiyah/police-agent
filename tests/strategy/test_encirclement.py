"""Tests for the medium-range barrier check: pocket-shrinking, not escape-removal."""

from police_agent.domain.board import Board
from police_agent.strategy.encirclement import ENDGAME_ROUNDS, wide_placement

# A doorway at (4, 0) is the sole connection between the open board and a
# 14-cell room filling rows 5-6. Sealing it strands the room without touching
# the direct route from the cop to a believed cell that never enters it.
_ROOM_BARRIERS = {(4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6)}


class TestWidePlacement:
    def test_seals_a_large_dead_end_off_the_direct_path(self):
        board = Board(7)
        cell = wide_placement(board, position=(3, 0), barriers=_ROOM_BARRIERS, believed=(3, 3))
        assert cell == (4, 0)

    def test_never_when_the_gain_is_too_small(self):
        # Open board, no pocket to shrink: any nearby wall trims a sliver at best.
        board = Board(5)
        assert wide_placement(board, position=(2, 1), barriers=set(), believed=(0, 0)) is None

    def test_never_when_it_would_confine_the_police(self):
        # The cop at (0, 0) on a 3x3 has exactly one open neighbour, (0, 1); the
        # only other candidate, (1, 0), is already a wall, so sealing (0, 1) too
        # would leave the cop with no legal step.
        board = Board(3)
        barriers = {(1, 0)}
        assert wide_placement(board, position=(0, 0), barriers=barriers, believed=(2, 2)) is None

    def test_never_when_it_would_cut_the_police_off_from_the_target(self):
        # Sealing the room's only doorway while the believed cell sits inside it
        # would maroon the target beyond the cop's own reach -- refused even
        # though the "gain" in isolation is large.
        board = Board(7)
        cell = wide_placement(board, position=(3, 0), barriers=_ROOM_BARRIERS, believed=(6, 6))
        assert cell is None

    def test_returns_none_past_a_gap_the_caller_never_offers(self):
        # wide_placement itself has no range gate -- `choose_barrier` is the one
        # that decides when to call it -- but a gain-based refusal still holds
        # regardless of distance when there is nothing to shrink.
        board = Board(7)
        assert wide_placement(board, position=(0, 0), barriers=set(), believed=(6, 6)) is None


class TestEndgameRelaxation:
    def test_omitting_rounds_left_keeps_the_ordinary_threshold(self):
        # Same open-board case as test_never_when_the_gain_is_too_small: no
        # signal means no relaxation, ever.
        board = Board(5)
        assert wide_placement(board, position=(2, 1), barriers=set(), believed=(0, 0)) is None

    def test_outside_the_endgame_window_the_ordinary_threshold_still_holds(self):
        board = Board(5)
        cell = wide_placement(
            board,
            position=(2, 1),
            barriers=set(),
            believed=(0, 0),
            rounds_left=ENDGAME_ROUNDS + 1,
        )
        assert cell is None

    def test_inside_the_endgame_window_a_trivial_gain_now_qualifies(self):
        # The exact scenario that was refused above: with only a few rounds
        # left, an unused barrier scores nothing anyway, so even a one-cell
        # shrink is worth the turn.
        board = Board(5)
        cell = wide_placement(
            board, position=(2, 1), barriers=set(), believed=(0, 0), rounds_left=ENDGAME_ROUNDS
        )
        assert cell is not None

    def test_still_never_confines_the_police_or_costs_ground_in_the_endgame(self):
        # The safety checks are not part of what the endgame window loosens --
        # only the gain bar is.
        board = Board(3)
        barriers = {(1, 0)}
        cell = wide_placement(
            board, position=(0, 0), barriers=barriers, believed=(2, 2), rounds_left=1
        )
        assert cell is None
