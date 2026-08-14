"""The belief map: a distribution that predicts, observes, and stays a distribution.

The property worth defending here is that every operation leaves a probability
distribution behind. A belief that stopped summing to one would still return an
argmax, and the chase would keep working while quietly meaning nothing.

Observing a scent reading is tested in `test_belief_observe.py`, and building
one from agreed terms in `test_belief_construction.py` -- split out to keep
each file inside the 150-line rule, the same way `test_belief_prediction.py`
and `test_belief_scale.py` already were.
"""

import pytest

from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.threat import ThreatEstimate


def total(belief: BeliefGrid) -> float:
    """The mass, rounded past float noise -- the invariant is "sums to one",
    not "sums to one in binary floating point"."""
    return round(sum(sum(row) for row in belief.as_matrix()), 9)


class TestDistribution:
    def test_it_satisfies_the_threat_protocol_the_brain_consumes(self):
        assert isinstance(BeliefGrid(7), ThreatEstimate)

    def test_knowing_nothing_is_a_flat_prior_over_every_cell(self):
        matrix = BeliefGrid(7).as_matrix()

        assert total(BeliefGrid(7)) == 1.0
        assert len({round(p, 12) for row in matrix for p in row}) == 1

    def test_every_update_leaves_a_distribution_behind(self):
        belief = BeliefGrid(7)

        belief.observe_smell({"2,3": 0.9})
        assert total(belief) == 1.0
        belief.diffuse()
        assert total(belief) == 1.0
        belief.exclude((2, 3))
        assert total(belief) == 1.0

    def test_a_collapsed_belief_resets_to_the_prior_rather_than_dividing_by_zero(self):
        belief = BeliefGrid(2)
        for cell in ((0, 0), (0, 1), (1, 0), (1, 1)):
            belief.exclude(cell)

        assert total(belief) == 1.0
        assert belief.as_matrix() == [[0.25, 0.25], [0.25, 0.25]]

    def test_a_board_must_have_cells(self):
        with pytest.raises(ValueError, match="must be positive"):
            BeliefGrid(0)
