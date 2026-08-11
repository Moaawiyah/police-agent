"""Tests for `BeliefGrid.top_cells`: reading more than the argmax off the map.

Split from test_belief.py to keep both files inside the 150-line rule.

The barrier policy weighs a wall against the top of the distribution rather than
its single peak, so the ordering has to be total, stable and recomputable -- a
placement is re-derived from the replayed state in the end-of-game audit.
"""

from police_agent.strategy.belief import BeliefGrid


def belief_with(size: int, peaks: dict) -> BeliefGrid:
    """A grid re-weighted so `peaks` maps a cell to its relative boost."""
    grid = BeliefGrid(size, leak=0.0)
    for cell, factor in peaks.items():
        grid.scale([cell], factor)
    return grid


class TestOrdering:
    def test_ranks_the_likeliest_cells_first(self):
        grid = belief_with(5, {(1, 1): 10.0, (3, 4): 5.0})
        assert [cell for cell, _ in grid.top_cells(2)] == [(1, 1), (3, 4)]

    def test_reports_each_cell_with_its_own_probability(self):
        grid = belief_with(5, {(1, 1): 10.0})
        cell, prob = grid.top_cells(1)[0]
        assert cell == (1, 1)
        assert prob == grid.as_matrix()[1][1]

    def test_the_head_of_the_ranking_is_the_argmax(self):
        grid = belief_with(5, {(2, 3): 7.0})
        assert grid.top_cells(1)[0][0] == grid.most_likely()

    def test_a_flat_prior_ties_row_major(self):
        """Every cell is equally likely, so the order is the tie-break alone --
        and it must be the same one `most_likely` has always used."""
        assert [cell for cell, _ in BeliefGrid(3).top_cells(3)] == [(0, 0), (0, 1), (0, 2)]


class TestCount:
    def test_defaults_to_the_single_likeliest_cell(self):
        assert len(belief_with(5, {(1, 1): 10.0}).top_cells()) == 1

    def test_never_returns_more_cells_than_the_board_holds(self):
        assert len(BeliefGrid(3).top_cells(100)) == 9

    def test_asking_for_none_returns_none(self):
        assert BeliefGrid(3).top_cells(0) == []


class TestDeterminism:
    def test_the_same_evidence_always_ranks_the_same(self):
        first = belief_with(5, {(1, 1): 10.0, (3, 4): 10.0}).top_cells(3)
        second = belief_with(5, {(1, 1): 10.0, (3, 4): 10.0}).top_cells(3)
        assert first == second
