"""The belief map: a distribution that predicts, observes, and stays a distribution.

The property worth defending here is that every operation leaves a probability
distribution behind. A belief that stopped summing to one would still return an
argmax, and the chase would keep working while quietly meaning nothing.
"""

from police_agent.peer.terms import terms_from_config
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.threat import ThreatEstimate
from tests.conftest import config_with


def total(belief: BeliefGrid) -> float:
    return sum(sum(row) for row in belief.as_matrix())


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
        import pytest

        with pytest.raises(ValueError, match="must be positive"):
            BeliefGrid(0)


class TestObserving:
    def test_the_strongest_reading_becomes_the_belief(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.2, "6,6": 0.9, "3,3": 0.5})

        assert belief.most_likely() == (6, 6)

    def test_silence_is_not_evidence_of_absence(self):
        """An empty grid must not wipe out what the last one established."""
        belief = BeliefGrid(7)
        belief.observe_smell({"1,1": 0.7})
        belief.observe_smell({})

        assert belief.most_likely() == (1, 1)

    def test_readings_accumulate_instead_of_replacing_each_other(self):
        """This is the whole difference from the argmax placeholder it replaced."""
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.9})
        belief.observe_smell({"5,5": 0.1})

        assert belief.most_likely() == (0, 0)

    def test_a_trail_is_still_remembered_a_turn_after_it_went_quiet(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"6,6": 0.9})

        belief.diffuse()
        belief.observe_smell({})

        row, col = belief.most_likely()
        assert abs(row - 6) + abs(col - 6) <= 1  # still on the thief, not back at the centre

    def test_junk_from_another_teams_implementation_is_skipped_not_fatal(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"not-a-cell": 0.9, "9,9": 0.9, "1,1": "loud", "2,4": 0.6})

        assert belief.most_likely() == (2, 4)
        assert total(belief) == 1.0

    def test_excluding_a_cell_rules_it_out_entirely(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"2,2": 0.9})
        belief.exclude((2, 2))

        assert belief.as_matrix()[2][2] == 0.0
        assert belief.most_likely() != (2, 2)

    def test_excluding_a_cell_off_the_board_is_ignored_not_fatal(self):
        belief = BeliefGrid(7)
        belief.exclude((9, 9))

        assert total(belief) == 1.0


class TestConstruction:
    def test_it_takes_the_board_from_the_agreed_terms_and_trust_from_the_private_file(self):
        config = config_with(belief__smell_trust=9.0)

        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert len(belief.as_matrix()) == 7
        assert belief._smell_trust == 9.0

    def test_an_unset_trust_falls_back_to_the_shipped_default(self, config):
        belief = BeliefGrid.from_config(terms_from_config(config), config)

        assert belief._smell_trust == 4.0
