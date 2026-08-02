"""What a verdict does to the belief map once it has been reached.

The behaviour ch. 4.4 exists to produce: a peer caught lying has its next
claim counted against the direction it names.
"""

from police_agent.constants import Direction
from police_agent.strategy.bearings import cells_toward, strongest_cell
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.bluff import BluffAnalyst

NORTH_HINT = "I slipped away northward, officer"
SOUTH_HINT = "gone south past the market"


def caught_lying(times: int = 6) -> BluffAnalyst:
    """An analyst that has watched this thief claim north while smelling of south."""
    analyst = BluffAnalyst()
    for _ in range(times):
        analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(4, 3))
    return analyst


def proved_honest(times: int = 6) -> BluffAnalyst:
    analyst = BluffAnalyst()
    for _ in range(times):
        analyst.assess(NORTH_HINT, believed=(3, 3), smelled=(2, 3))
    return analyst


class TestApplyingAVerdict:
    def test_a_trusted_claim_pulls_the_belief_the_way_it_points(self):
        analyst = proved_honest()
        belief = BeliefGrid(7)

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=None)
        analyst.apply(verdict, belief, origin=(3, 3))

        matrix = belief.as_matrix()
        assert matrix[0][3] > matrix[6][3]  # north of the origin now outweighs south

    def test_a_liars_claim_pushes_the_belief_the_other_way(self):
        """The point of ch. 4.4: a known liar naming north is evidence of south."""
        analyst = caught_lying()
        belief = BeliefGrid(7)

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=None)
        analyst.apply(verdict, belief, origin=(3, 3))

        matrix = belief.as_matrix()
        assert matrix[0][3] < matrix[6][3]

    def test_an_unproven_opponent_leaves_the_belief_exactly_as_it_was(self):
        belief, untouched = BeliefGrid(7), BeliefGrid(7)
        analyst = BluffAnalyst()

        verdict = analyst.assess(NORTH_HINT, believed=(3, 3), smelled=None)
        analyst.apply(verdict, belief, origin=(3, 3))

        assert belief.as_matrix() == untouched.as_matrix()

    def test_applying_a_verdict_leaves_a_distribution_behind(self):
        belief = BeliefGrid(7)
        analyst = caught_lying()

        analyst.apply(analyst.assess(SOUTH_HINT, (3, 3), None), belief, origin=(3, 3))

        assert round(sum(sum(row) for row in belief.as_matrix()), 9) == 1.0


class TestFindingTheTrail:
    def test_the_freshest_cell_is_the_one_that_judges_the_claim(self):
        assert strongest_cell({"1,1": 0.2, "5,3": 0.9, "4,3": 0.62}) == (5, 3)

    def test_a_silent_turn_has_no_trail_to_judge_against(self):
        assert strongest_cell({}) is None
        assert strongest_cell(None) is None

    def test_junk_from_another_teams_implementation_is_skipped_not_fatal(self):
        assert strongest_cell({"bad": 1.0, "2,4": 0.6, "1,1": "loud"}) == (2, 4)

    def test_ties_resolve_the_same_way_for_both_peers(self):
        assert strongest_cell({"5,5": 0.5, "1,1": 0.5}) == (1, 1)


class TestTheHalfPlaneAClaimPointsAt:
    def test_north_is_every_row_above_the_origin(self):
        assert cells_toward((3, 3), Direction.N, 7) == [
            (row, col) for row in (0, 1, 2) for col in range(7)
        ]

    def test_south_is_every_row_below_it(self):
        assert all(row > 3 for row, _ in cells_toward((3, 3), Direction.S, 7))

    def test_west_is_every_column_left_of_it(self):
        assert all(col < 3 for _, col in cells_toward((3, 3), Direction.W, 7))

    def test_east_is_every_column_right_of_it(self):
        assert all(col > 3 for _, col in cells_toward((3, 3), Direction.E, 7))

    def test_a_claim_pointing_off_the_board_selects_nothing(self):
        assert cells_toward((0, 0), Direction.N, 7) == []
