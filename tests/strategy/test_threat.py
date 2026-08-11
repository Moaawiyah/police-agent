"""Tests for the threat estimate: the only thing strategy may know about the thief."""

import pytest

from police_agent.strategy.threat import PointThreat, ThreatEstimate, UniformThreat


class TestPointThreat:
    def test_reports_the_cell_it_was_given(self):
        assert PointThreat((2, 5)).most_likely() == (2, 5)

    def test_is_stable_across_calls(self):
        threat = PointThreat((0, 0))
        assert threat.most_likely() == threat.most_likely()

    def test_a_known_target_counts_as_evidence(self):
        assert PointThreat((0, 0)).has_scent() is True

    def test_offers_its_one_cell_at_full_weight(self):
        assert PointThreat((2, 5)).top_cells(3) == [((2, 5), 1.0)]

    def test_excluding_the_fixed_cell_does_not_change_it(self):
        threat = PointThreat((2, 5))
        threat.exclude((2, 5))
        assert threat.most_likely() == (2, 5)


class TestUniformThreat:
    def test_flat_prior_points_at_the_board_centre(self):
        assert UniformThreat(7).most_likely() == (3, 3)

    def test_an_untouched_prior_is_not_evidence(self):
        assert UniformThreat(7).has_scent() is False

    def test_even_boards_round_toward_the_low_corner(self):
        assert UniformThreat(8).most_likely() == (3, 3)

    def test_single_cell_board_is_its_own_centre(self):
        assert UniformThreat(1).most_likely() == (0, 0)

    def test_rejects_an_impossible_board(self):
        with pytest.raises(ValueError, match="positive"):
            UniformThreat(0)

    def test_offers_only_the_centre_because_a_flat_ranking_is_noise(self):
        assert UniformThreat(7).top_cells(5) == [((3, 3), 1.0)]

    def test_excluding_a_cell_leaves_the_flat_prior_flat(self):
        threat = UniformThreat(7)
        threat.exclude((0, 0))
        assert threat.most_likely() == (3, 3)


class TestProtocol:
    """The interface is structural: answering the three calls is the whole contract."""

    def test_the_shipped_estimates_satisfy_it(self):
        assert isinstance(PointThreat((1, 1)), ThreatEstimate)
        assert isinstance(UniformThreat(5), ThreatEstimate)

    def test_an_unrelated_class_that_answers_every_call_also_satisfies_it(self):
        class FakeBelief:
            def diffuse(self):
                pass

            def observe_smell(self, cells):
                pass

            def scale(self, cells, factor):
                pass

            def exclude(self, cell):
                pass

            def most_likely(self):
                return (4, 4)

            def top_cells(self, count=1):
                return [((4, 4), 1.0)]

            def has_scent(self):
                return True

        assert isinstance(FakeBelief(), ThreatEstimate)

    def test_answering_only_most_likely_is_not_enough(self):
        """The turn loop calls all three, so a partial estimate fails mid-match."""

        class HalfABelief:
            def most_likely(self):
                return (4, 4)

        assert not isinstance(HalfABelief(), ThreatEstimate)

    def test_a_class_without_most_likely_does_not(self):
        class NotABelief:
            pass

        assert not isinstance(NotABelief(), ThreatEstimate)
