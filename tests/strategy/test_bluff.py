"""Deciding how much of the thief's talk to believe, and acting on the answer.

The behaviour under test is ch. 4.4's: a claim is checked against the scent, a
peer that is caught lying stops being believed, and its later claims start
counting *against* the direction they name.
"""

from police_agent.strategy.bluff import BluffAnalyst

NORTH_HINT = "I slipped away northward, officer"


def caught_lying(times: int = 6) -> BluffAnalyst:
    """An analyst that has watched this thief claim north and go south."""
    analyst = BluffAnalyst()
    for _ in range(times):
        analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(4, 3))  # said north, went south
    return analyst


def proved_honest(times: int = 6) -> BluffAnalyst:
    analyst = BluffAnalyst()
    for _ in range(times):
        analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(2, 3))  # said north, went north
    return analyst


class TestJudgingAClaimAgainstTheScent:
    def test_a_claim_the_scent_bears_out_is_corroborated(self):
        analyst = BluffAnalyst()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(2, 3))

        assert verdict.corroborated is True
        assert (analyst.corroborated, analyst.contradicted) == (1, 0)

    def test_a_claim_the_scent_refutes_is_contradicted(self):
        analyst = BluffAnalyst()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(4, 3))

        assert verdict.corroborated is False
        assert (analyst.corroborated, analyst.contradicted) == (0, 1)

    def test_movement_on_the_other_axis_proves_nothing_either_way(self):
        analyst = BluffAnalyst()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(3, 5))

        assert verdict.corroborated is None
        assert (analyst.corroborated, analyst.contradicted) == (0, 0)

    def test_a_diagonal_still_corroborates_on_the_axis_that_was_claimed(self):
        """It said north and it went north; whatever else it did is not a lie."""
        analyst = BluffAnalyst()

        assert analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(2, 5)).corroborated is True

    def test_a_hint_claiming_no_direction_is_not_scored(self):
        analyst = BluffAnalyst()

        verdict = analyst.assess("catch me if you can", believed=(3, 3), smelled=(2, 3))

        assert verdict.direction is None
        assert (analyst.corroborated, analyst.contradicted) == (0, 0)

    def test_every_reading_leaves_a_line_for_the_report(self):
        assert "corroborated" in BluffAnalyst().assess(NORTH_HINT, (3, 3), (2, 3)).note


class TestReliability:
    def test_an_unproven_opponent_is_neither_believed_nor_disbelieved(self):
        analyst = BluffAnalyst()

        assert analyst.reliability == 0.5
        assert analyst.trust == 0.0

    def test_being_caught_out_costs_the_thief_its_credibility(self):
        assert caught_lying().reliability < 0.5
        assert caught_lying().trust < 0.0

    def test_telling_the_truth_earns_it_back(self):
        assert proved_honest().reliability > 0.5
        assert proved_honest().trust > 0.0

    def test_one_honest_hint_is_not_yet_an_honest_opponent(self):
        """Smoothing is what stops the first hint deciding everything."""
        analyst = BluffAnalyst()
        analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(2, 3))

        assert analyst.reliability < 0.7


class TestWhenTheHintMovesTheBelief:
    def test_a_claim_the_trail_already_answered_does_not_count_twice(self):
        """The scent is about to move the belief; letting the hint move it too
        counts one turn's evidence twice."""
        analyst = proved_honest()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(2, 3))

        assert verdict.trust == 0.0

    def test_with_nothing_smelled_the_claim_is_all_there_is(self):
        analyst = proved_honest()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=None)

        assert verdict.trust > 0.0

    def test_an_unproven_opponent_still_moves_nothing(self):
        analyst = BluffAnalyst()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=None)

        assert verdict.trust == 0.0
