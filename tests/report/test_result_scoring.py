"""Per-sub-game and series scoring, split out of test_result.py to keep both
files under the project's 150-line rule; fixtures are defined there and
imported here.
"""

from police_agent.report.facts import facts_from
from police_agent.report.result import DEFAULT_SCORING, build_result, scoring_from, subgame_block
from tests.conftest import config_with
from tests.report.test_result import POLICE, THIEF, _capture, _result


class TestScoringTheSeries:
    def test_each_sub_game_is_scored_from_the_signed_table(self):
        """A capture is 20 to whoever policed it and 5 to whoever was caught."""
        artifact = _result()

        assert artifact["sub_games"][0]["score"] == {POLICE: 20, THIEF: 5}

    def test_the_winner_is_reported_as_a_group_not_as_a_role(self):
        """Roles swap across the series, so only the group id means the same twice."""
        artifact = _result()

        assert artifact["sub_games"][0]["winner_group"] == POLICE
        assert artifact["sub_games"][1]["winner_group"] == THIEF

    def test_the_totals_are_the_sub_games_summed(self):
        artifact = _result()

        assert artifact["final_result"]["total_score"] == {POLICE: 25, THIEF: 15}
        assert artifact["final_result"]["winner_group"] == POLICE
        assert artifact["final_result"]["sub_games_won"] == {POLICE: 1, THIEF: 1}

    def test_a_sub_game_nobody_won_scores_the_technical_loss_for_both(self):
        summary = {**_capture(), "result": "technical_loss", "winner": None}

        block = subgame_block(summary, DEFAULT_SCORING)

        assert block["score"] == {POLICE: 0, THIEF: 0}
        assert block["winner_group"] is None
        assert block["tie"] is False

    def test_a_tamper_forfeit_is_zeroed_not_credited_to_the_catcher(self):
        """The interop kit's binding table: tamper forfeit zeroes both sides,
        the same as timeout/technical_loss -- it is a sanction, not a win, even
        though the runtime's own `summary["winner"]` names the honest peer."""
        summary = {**_capture(), "result": "tamper_forfeit", "winner": "police"}

        block = subgame_block(summary, DEFAULT_SCORING)

        assert block["score"] == {POLICE: 0, THIEF: 0}
        assert block["winner_group"] is None
        assert block["tie"] is False

    def test_a_tamper_forfeit_counts_toward_neither_sub_games_won_nor_ties(self):
        """A zeroed sub-game is credited to nobody: sub_games_won[a] +
        sub_games_won[b] + ties + zeroed == num_sub_games (the count of
        zeroed sub-games isn't a tracked field, so it must show up as neither
        of the other two). A real capture sits alongside it so the series
        isn't degenerately all-zeroed."""
        forfeited = {
            **_capture(),
            "result": "tamper_forfeit",
            "winner": "police",
            "step_zero": {"sub_game_number": 2},
        }
        summaries = [_capture(), forfeited]

        artifact = build_result(facts_from(summaries[0]), summaries)

        assert artifact["final_result"]["sub_games_won"] == {POLICE: 1, THIEF: 0}
        assert artifact["final_result"]["ties"] == 0

    def test_the_signed_table_is_used_when_one_was_loaded(self):
        assert scoring_from(config_with()) == config_with().get("scoring")

    def test_appendix_vavs_mandatory_values_stand_in_when_none_was(self):
        """A report that refused to be produced over one missing point value
        would cost both teams the match."""
        assert scoring_from()["capture_cop"] == 20
        assert scoring_from(config_with(scoring=None))["survival_thief"] == 10
