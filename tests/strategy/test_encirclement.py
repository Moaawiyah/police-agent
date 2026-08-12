"""Tests for the pocket-shrink bar: when a wall that removes no escape is worth a turn.

The bar itself lives in `strategy/encirclement.py`; `strategy/placement.py` is
what applies it, so the refusals are asserted through `best_placement`.
"""

from police_agent.domain.board import Board
from police_agent.strategy.encirclement import MIN_GAIN_FLOOR, pocket_bar
from police_agent.strategy.placement import best_placement

# A doorway at (4, 0) is the sole connection between the open board and a
# 14-cell room filling rows 5-6. Sealing it strands the room without touching
# the direct route from the cop to a believed cell that never enters it.
_ROOM_BARRIERS = {(4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6)}


def place(board, position, barriers, believed):
    """`best_placement` with all the belief on the single believed cell."""
    return best_placement(board, position, barriers, believed, [(believed, 1.0)])


class TestPocketBar:
    def test_scales_with_the_pocket_it_is_measured_against(self):
        board = Board(7)
        assert pocket_bar(board, (3, 3), set()) == int(49 * 0.22)

    def test_never_drops_below_the_floor_on_a_tiny_pocket(self):
        # A 3x3 board's whole area is 9; a fraction of that rounds under the floor.
        assert pocket_bar(Board(3), (1, 1), set()) == MIN_GAIN_FLOOR


class TestSealingAPocket:
    def test_seals_a_large_dead_end_off_the_direct_path(self):
        board = Board(7)
        found = place(board, (3, 0), _ROOM_BARRIERS, (3, 3))
        assert found == ((4, 0), False)  # a seal, not an escape removal

    def test_never_when_the_gain_is_too_small(self):
        # Open board, no pocket to shrink: any nearby wall trims a sliver at best.
        assert place(Board(5), (2, 1), set(), (0, 0)) is None

    def test_never_when_it_would_confine_the_police(self):
        # The cop at (0, 0) on a 3x3 has exactly one open neighbour, (0, 1); the
        # only other candidate, (1, 0), is already a wall, so sealing (0, 1) too
        # would leave the cop with no legal step.
        assert place(Board(3), (0, 0), {(1, 0)}, (2, 2)) is None

    def test_never_when_it_would_cut_the_police_off_from_the_target(self):
        # Sealing the room's only doorway while the believed cell sits inside it
        # would maroon the target beyond the cop's own reach -- refused even
        # though the "gain" in isolation is large.
        assert place(Board(7), (3, 0), _ROOM_BARRIERS, (6, 6)) is None

    def test_refuses_when_there_is_simply_nothing_to_shrink(self):
        # `best_placement` has no range gate -- `choose_barrier` is the one that
        # decides when to call it -- but a gain-based refusal holds regardless
        # of distance when no wall takes anything away.
        assert place(Board(7), (0, 0), set(), (6, 6)) is None

    def test_the_gain_bar_holds_even_on_the_last_reachable_round(self):
        # No `rounds_left` signal exists: the same marginal wall that is refused
        # in round one is refused in the match's final round too.
        assert place(Board(5), (2, 1), set(), (0, 0)) is None
