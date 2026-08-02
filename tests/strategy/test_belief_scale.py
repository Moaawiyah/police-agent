"""Reweighting arbitrary cells: the update step opened up for non-scent evidence.

Whatever a caller believes it has learned, the grid it hands back must still
be a probability distribution -- that is the only promise `scale` makes.
"""

from police_agent.strategy.belief import BeliefGrid


def total(belief: BeliefGrid) -> float:
    """Rounded past float noise: the invariant is "sums to one"."""
    return round(sum(sum(row) for row in belief.as_matrix()), 9)


class TestScaling:
    def test_reweighted_cells_gain_on_the_rest(self):
        belief = BeliefGrid(7)
        belief.scale([(0, 0), (0, 1)], 4.0)

        matrix = belief.as_matrix()
        assert matrix[0][0] > matrix[3][3]
        assert matrix[0][0] == matrix[0][1]

    def test_a_factor_below_one_gives_the_weight_away(self):
        belief = BeliefGrid(7)
        belief.scale([(0, 0)], 0.5)

        assert belief.as_matrix()[0][0] < belief.as_matrix()[3][3]

    def test_it_is_still_a_distribution_afterwards(self):
        belief = BeliefGrid(7)
        belief.scale([(1, 1), (2, 2)], 3.0)

        assert total(belief) == 1.0

    def test_cells_off_the_board_are_ignored_rather_than_fatal(self):
        belief = BeliefGrid(7)
        belief.scale([(9, 9), (-1, 0), (1, 1)], 2.0)

        assert total(belief) == 1.0

    def test_scaling_everything_to_nothing_resets_rather_than_dividing_by_zero(self):
        belief = BeliefGrid(3)
        belief.scale([(row, col) for row in range(3) for col in range(3)], 0.0)

        assert total(belief) == 1.0
