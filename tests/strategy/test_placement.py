"""Tests for the wall scorer: every candidate is ranked, not just the first legal one.

The point of ranking only shows up when the belief is spread. Two candidates
that each take one escape away from a single known cell score identically, so
board order still decides between them -- as it always did. What changes the
answer is a candidate that stands next to *more of the distribution*, which is
what `top_cells` supplies and what the paired tests below pin down.
"""

from police_agent.constants import Direction
from police_agent.domain.board import Board
from police_agent.strategy.placement import best_placement

# A doorway at (4, 0) is the sole connection between the open board and a
# 14-cell room filling rows 5-6.
_ROOM_BARRIERS = {(4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6)}


class TestRankingBeatsBoardOrder:
    """The police at (3, 3) with the thief believed at (2, 4): (2, 3) and (3, 4)
    are the two cells adjacent to both, and the board offers (2, 3) first (N
    before E). Each takes exactly one escape from (2, 4), so on a point belief
    they tie and the board order stands."""

    def test_a_point_belief_still_answers_with_the_first_in_board_order(self):
        found = best_placement(Board(7), (3, 3), set(), (2, 4), [((2, 4), 1.0)])
        assert found == ((2, 3), True)

    def test_a_spread_belief_prefers_the_wall_touching_more_of_it(self):
        # Half the mass sits at (4, 4), which (3, 4) is also adjacent to and
        # (2, 3) is not -- so (3, 4) removes an escape from both plausible
        # cells and wins, even though the board offers (2, 3) first.
        belief = [((2, 4), 0.5), ((4, 4), 0.5)]
        found = best_placement(Board(7), (3, 3), set(), (2, 4), belief)
        assert found == ((3, 4), True)


class TestBothScoreTerms:
    def test_a_wall_that_takes_no_escape_can_still_win_at_close_range(self):
        # The police is one step from the believed thief, so this is the close
        # chase -- but neither candidate touches an escape. (4, 0) seals the
        # 14-cell room off instead, which is worth the turn on area alone.
        found = best_placement(Board(7), (3, 0), _ROOM_BARRIERS, (3, 1), [((3, 1), 1.0)])
        assert found == ((4, 0), False)

    def test_removing_an_escape_outranks_a_sliver_of_area(self):
        found = best_placement(Board(7), (3, 3), set(), (2, 4), [((2, 4), 1.0)])
        assert found is not None and found[1] is True


class TestBeliefWeights:
    def test_unnormalised_weights_answer_the_same_as_normalised_ones(self):
        board = Board(7)
        raw = best_placement(board, (3, 3), set(), (2, 4), [((2, 4), 5.0), ((4, 4), 5.0)])
        normalised = best_placement(board, (3, 3), set(), (2, 4), [((2, 4), 0.5), ((4, 4), 0.5)])
        assert raw == normalised

    def test_a_belief_with_no_mass_falls_back_to_the_primary_cell(self):
        board = Board(7)
        empty = best_placement(board, (3, 3), set(), (2, 4), [((2, 4), 0.0), ((4, 4), 0.0)])
        assert empty == best_placement(board, (3, 3), set(), (2, 4), [((2, 4), 1.0)])

    def test_a_wall_forfeits_the_belief_mass_sitting_on_its_own_cell(self):
        """A cell cannot both be walled and be where the thief is standing, so a
        candidate earns nothing from belief mass on itself.

        (2, 3) and (3, 4) tie on a point belief at (2, 4). Move half the mass
        onto (2, 3) and the tie breaks *against* (2, 3): walling it collects
        nothing from that half, while (3, 4) still collects it."""
        board = Board(7)
        found = best_placement(board, (3, 3), set(), (2, 4), [((2, 4), 0.5), ((2, 3), 0.5)])
        assert found == ((3, 4), True)


class TestSafetyRulesAreAbsolute:
    def test_never_walls_the_cell_underfoot(self):
        # Standing next to a cornered thief whose only escape is our own cell:
        # walling it would deny us the one cell we are certain to be on.
        board = Board(3)
        barriers = {(1, 0), (1, 1), (0, 2)}
        assert board.legal_moves((0, 0), barriers) == [(Direction.E, (0, 1))]
        assert best_placement(board, (0, 1), barriers, (0, 0), [((0, 0), 1.0)]) is None

    def test_never_walls_the_believed_cell_itself(self):
        found = best_placement(Board(7), (3, 3), set(), (3, 4), [((3, 4), 1.0)])
        assert found is None or found[0] != (3, 4)

    def test_refuses_everything_when_the_target_is_already_unreachable(self):
        # The believed cell is sealed inside the room; no wall of ours can help
        # a chase that has no path to walk in the first place.
        board = Board(7)
        sealed = _ROOM_BARRIERS | {(4, 0)}
        assert best_placement(board, (3, 0), sealed, (6, 6), [((6, 6), 1.0)]) is None

    def test_the_last_escape_may_cost_ground_but_nothing_else_may(self):
        # (1, 0) is walled, so (0, 1) is the thief's only way out of (0, 0), and
        # sealing it is the capture -- allowed even though it lengthens our own
        # path. The other candidates take no escape and are held to the bar.
        board = Board(5)
        found = best_placement(board, (1, 1), {(1, 0)}, (0, 0), [((0, 0), 1.0)])
        assert found == ((0, 1), True)
