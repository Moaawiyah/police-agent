"""The binding report: identifiers, repository links, and per-sub-game scoring.

Rule 35 makes this the expensive artifact to get wrong: if either team's report
is missing or disagrees, *neither* team scores for the match. The symmetric
mutual-agreement digest -- the actual weight-bearing part -- lives in
test_result_digest.py, split out to keep both files under the project's
150-line rule; its fixtures are defined here and imported there.
"""

from police_agent.report.facts import facts_from
from police_agent.report.ids import SCHEMA_VERSION
from police_agent.report.result import (
    DEFAULT_SCORING,
    RESULT_TYPE,
    build_result,
    scoring_from,
    subgame_block,
)
from tests.conftest import config_with

POLICE, THIEF = "police-team", "thief-team"
TERMS = {"board_size": 7, "num_games": 2}
OUR_REPOS = {"cop": "https://example.test/cop", "thief": "https://example.test/thief"}
THEIR_REPOS = {"cop": "https://example.test/their-cop", "thief": "https://example.test/their-thief"}


class TestWhatTheLecturerIsSent:
    def test_it_names_itself_and_the_schema_it_follows(self):
        artifact = _result()

        assert artifact["artifact_type"] == RESULT_TYPE
        assert artifact["schema_version"] == SCHEMA_VERSION

    def test_it_carries_the_identifiers_the_four_files_are_joined_on(self):
        facts = facts_from(_summary())

        artifact = build_result(facts, [_summary()])

        assert (artifact["game_uid"], artifact["game_id"]) == (facts.game_uid, facts.game_id)

    def test_it_carries_all_four_repository_links_as_chapter_nine_four_requires(self):
        artifact = _result()

        assert artifact["repos"] == {POLICE: OUR_REPOS, THIEF: THEIR_REPOS}

    def test_it_carries_the_commit_each_group_played_per_sub_game(self):
        """Rule 53: a team may change its code between sub-games."""
        artifact = _result()

        assert artifact["sub_games"][0]["github_commits"] == {POLICE: "a" * 40, THIEF: "b" * 40}
        assert artifact["sub_games"][1]["github_commits"][POLICE] == "c" * 40

    def test_it_reports_the_series_length_played_against_the_one_agreed(self):
        artifact = _result()

        assert artifact["sub_games_played"] == 2
        assert artifact["num_sub_games_agreed"] == 2


class TestScoringTheSeries:
    def test_each_sub_game_is_scored_from_the_signed_table(self):
        """A capture is 20 to whoever policed it and 5 to whoever was caught."""
        artifact = _result()

        assert artifact["sub_games"][0]["scores"] == {POLICE: 20, THIEF: 5}

    def test_the_winner_is_reported_as_a_group_not_as_a_role(self):
        """Roles swap across the series, so only the group id means the same twice."""
        artifact = _result()

        assert artifact["sub_games"][0]["winner_group"] == POLICE
        assert artifact["sub_games"][1]["winner_group"] == THIEF

    def test_the_totals_are_the_sub_games_summed(self):
        artifact = _result()

        assert artifact["totals"]["total_score"] == {POLICE: 25, THIEF: 15}
        assert artifact["totals"]["winner_group"] == POLICE
        assert artifact["totals"]["sub_games_won"] == {POLICE: 1, THIEF: 1}

    def test_a_sub_game_nobody_won_scores_the_technical_loss_for_both(self):
        summary = {**_capture(), "result": "technical_loss", "winner": None}

        block = subgame_block(summary, DEFAULT_SCORING)

        assert block["scores"] == {POLICE: 0, THIEF: 0}
        assert block["winner_group"] is None

    def test_the_signed_table_is_used_when_one_was_loaded(self):
        assert scoring_from(config_with()) == config_with().get("scoring")

    def test_appendix_vavs_mandatory_values_stand_in_when_none_was(self):
        """A report that refused to be produced over one missing point value
        would cost both teams the match."""
        assert scoring_from()["capture_cop"] == 20
        assert scoring_from(config_with(scoring=None))["survival_thief"] == 10


def digest(summaries: list) -> str:
    return build_result(facts_from(summaries[0]), summaries)["mutual_agreement"]["sha256"]


def _result() -> dict:
    return build_result(facts_from(_capture()), _series(), config_with().get("scoring"))


def _series() -> list:
    return [_capture(), _survival()]


def _mirrored() -> list:
    """The same two sub-games as the thief's process holds them."""
    return [
        {
            **summary,
            "role": "thief",
            "identity": summary["peer_identity"],
            "peer_identity": summary["identity"],
            "started_at": "2026-08-05T09:00:03+00:00",
            "tokens": {"tokens_total": 42},
        }
        for summary in _series()
    ]


def _capture() -> dict:
    return _summary()


def _survival() -> dict:
    return {
        **_summary(),
        "result": "survival",
        "winner": "thief",
        "steps": 35,
        "step_zero": {"sub_game_number": 2},
        "identity": {**_summary()["identity"], "github_commit": "c" * 40},
    }


def _summary() -> dict:
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "steps": 12,
        "identity": {"group_id": POLICE, "repos": OUR_REPOS, "github_commit": "a" * 40},
        "peer_identity": {"group_id": THIEF, "repos": THEIR_REPOS, "github_commit": "b" * 40},
        "terms": TERMS,
        "step_zero": {"sub_game_number": 1},
        "started_at": "2026-08-05T09:00:00+00:00",
        "ended_at": "2026-08-05T09:02:00+00:00",
        "duration_seconds": 4.2,
        "tokens": {"tokens_total": 150, "budget_per_series": 200000},
        "audit": {"passed": True},
    }
