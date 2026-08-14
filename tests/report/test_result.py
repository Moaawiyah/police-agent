"""The binding report: identifiers and repository links.

Rule 35 makes this the expensive artifact to get wrong: if either team's report
is missing or disagrees, *neither* team scores for the match. Per-sub-game
scoring lives in test_result_scoring.py and the symmetric mutual-agreement
digest -- the actual weight-bearing part -- in test_result_digest.py, both
split out to keep every file under the project's 150-line rule; fixtures are
defined here and imported there.
"""

from police_agent.report.facts import facts_from
from police_agent.report.ids import SCHEMA_VERSION
from police_agent.report.result import RESULT_TYPE, build_result
from tests.conftest import config_with

POLICE, THIEF = "police-team", "thief-team"
TERMS = {"board_size": 7, "num_games": 2}
OUR_REPOS = {"cop": "https://example.test/cop", "thief": "https://example.test/thief"}
THEIR_REPOS = {"cop": "https://example.test/their-cop", "thief": "https://example.test/their-thief"}


class TestWhatTheLecturerIsSent:
    def test_it_names_itself_and_the_schema_it_follows(self):
        artifact = _result()

        assert artifact["report_type"] == RESULT_TYPE
        assert artifact["schema_version"] == SCHEMA_VERSION

    def test_it_carries_the_identifiers_the_four_files_are_joined_on(self):
        facts = facts_from(_summary())

        artifact = build_result(facts, [_summary()])

        assert (artifact["game_uid"], artifact["game_id"]) == (facts.game_uid, facts.game_id)

    def test_it_carries_all_four_repository_links_as_chapter_nine_four_requires(self):
        artifact = _result()

        assert artifact["repositories"] == {POLICE: OUR_REPOS, THIEF: THEIR_REPOS}

    def test_it_carries_the_commit_each_group_played_per_sub_game(self):
        """Rule 53: a team may change its code between sub-games."""
        artifact = _result()

        assert artifact["sub_games"][0]["github_commit"] == {POLICE: "a" * 40, THIEF: "b" * 40}
        assert artifact["sub_games"][1]["github_commit"][POLICE] == "c" * 40

    def test_it_reports_the_series_length_played_against_the_one_agreed(self):
        artifact = _result()

        assert artifact["num_sub_games"] == 2
        assert artifact["num_sub_games_agreed"] == 2


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
