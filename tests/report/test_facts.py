"""`ReportFacts`: the shared read-out of a match record, split out of
test_ids.py to keep both files under the project's line budget.
"""

from police_agent.report.facts import UNKNOWN_GROUP, ReportFacts, facts_from
from police_agent.report.ids import SCHEMA_VERSION
from tests.report.test_ids import POLICE, TERMS, THIEF


class TestTheSharedFacts:
    def test_they_are_read_out_of_a_match_record(self):
        facts = facts_from(_summary())

        assert facts.own_group_id == POLICE
        assert facts.opponent_group_id == THIEF
        assert facts.game_id == "police-team-vs-thief-team"
        assert facts.sub_game_number == 2

    def test_a_match_that_never_agreed_still_produces_a_report(self):
        """The failed match is exactly the one whose report the grader needs."""
        facts = facts_from({"identity": {"group_id": POLICE}})

        assert facts.opponent_group_id == UNKNOWN_GROUP
        assert facts.game_id

    def test_the_groups_are_listed_sorted(self):
        assert facts_from(_summary()).groups == [POLICE, THIEF]

    def test_the_links_block_is_built_from_the_match_name(self):
        facts = facts_from(_summary())

        assert facts.links["result"] == f"result_{facts.game_id}.json"

    def test_the_budget_and_sub_game_count_come_from_the_record(self):
        facts = facts_from(_summary())

        assert facts.token_budget == 200000
        assert facts.num_sub_games == 3

    def test_a_fact_cannot_be_adjusted_by_one_builder(self):
        facts = facts_from(_summary())

        try:
            facts.game_id = "something-else"
        except (AttributeError, TypeError):
            return
        raise AssertionError("ReportFacts is meant to be frozen")

    def test_the_schema_version_is_the_artifacts_own(self):
        """Not this project's version and not the config file's."""
        assert SCHEMA_VERSION == "1.1"
        assert isinstance(ReportFacts.timezone, str)


def _summary() -> dict:
    return {
        "identity": {"group_id": POLICE},
        "peer_identity": {"group_id": THIEF},
        "terms": {**TERMS, "num_games": 3},
        "step_zero": {"sub_game_number": 2},
        "started_at": "2026-08-05T09:00:00+00:00",
        "ended_at": "2026-08-05T09:02:00+00:00",
        "tokens": {"budget_per_series": 200000},
    }
