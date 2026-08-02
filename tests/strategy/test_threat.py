"""Tests for the threat estimate: the only thing strategy may know about the thief."""

import pytest

from police_agent.strategy.threat import PointThreat, ThreatEstimate, UniformThreat


class TestPointThreat:
    def test_reports_the_cell_it_was_given(self):
        assert PointThreat((2, 5)).most_likely() == (2, 5)

    def test_is_stable_across_calls(self):
        threat = PointThreat((0, 0))
        assert threat.most_likely() == threat.most_likely()


class TestUniformThreat:
    def test_flat_prior_points_at_the_board_centre(self):
        assert UniformThreat(7).most_likely() == (3, 3)

    def test_even_boards_round_toward_the_low_corner(self):
        assert UniformThreat(8).most_likely() == (3, 3)

    def test_single_cell_board_is_its_own_centre(self):
        assert UniformThreat(1).most_likely() == (0, 0)

    def test_rejects_an_impossible_board(self):
        with pytest.raises(ValueError, match="positive"):
            UniformThreat(0)


class TestProtocol:
    """The interface is structural: answering the three calls is the whole contract."""

    def test_the_shipped_estimates_satisfy_it(self):
        assert isinstance(PointThreat((1, 1)), ThreatEstimate)
        assert isinstance(UniformThreat(5), ThreatEstimate)

    def test_an_unrelated_class_that_answers_the_three_calls_also_satisfies_it(self):
        class FakeBelief:
            def diffuse(self):
                pass

            def observe_smell(self, cells):
                pass

            def most_likely(self):
                return (4, 4)

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
