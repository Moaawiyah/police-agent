"""Where the four artifacts land, under what names, and what the result covers.

The filenames are not decoration: ch. 9.3.3 derives every one of them from the
`game_id` so that files from different matches can never be mixed, and the
lecturer's tooling joins the set on the `game_uid` inside them. So the tests here
are about names, about the four files agreeing with each other, and about the
series -- a result artifact that only knew the sub-game its own process played
would be wrong in exactly the way rule 51 punishes.
"""

import json

from police_agent.report.facts import facts_from
from police_agent.report.ids import game_id
from police_agent.report.writer import artifact_paths, report_dir, series_records, write_artifacts
from tests.conftest import config_with

POLICE, THIEF = "police-team", "thief-team"


class TestWhereTheFilesLand:
    def test_each_group_gets_its_own_folder(self, tmp_path):
        """One machine can play both sides of a practice match; the two teams'
        reports must not end up in one pile."""
        paths = write_artifacts(_summary(), tmp_path)

        assert all(path.parent == tmp_path / POLICE for path in paths.values())

    def test_the_folder_is_created_rather_than_required(self, tmp_path):
        directory = report_dir(tmp_path / "nested" / "deeper", POLICE)

        assert directory.is_dir()

    def test_the_match_level_files_are_named_for_the_match(self, tmp_path):
        paths = write_artifacts(_summary(), tmp_path)

        assert paths["declaration"].name == f"declaration_{_game_id()}.json"
        assert paths["result"].name == f"result_{_game_id()}.json"

    def test_the_per_sub_game_files_carry_the_padded_sub_game_number(self, tmp_path):
        paths = write_artifacts(_summary(sub_game=7), tmp_path)

        assert paths["config"].name == f"config_{_game_id()}_g07.json"
        assert paths["log"].name == f"log_{_game_id()}_g07.json"

    def test_every_file_is_readable_json(self, tmp_path):
        paths = write_artifacts(_summary(), tmp_path)

        assert all(json.loads(path.read_text(encoding="utf-8")) for path in paths.values())

    def test_the_four_artifacts_agree_about_which_game_they_describe(self, tmp_path):
        """What the lecturer's tooling joins the set on."""
        paths = write_artifacts(_summary(), tmp_path)

        uids = {json.loads(paths[role].read_text())["game_uid"] for role in _SCHEMA_ARTIFACTS}
        assert len(uids) == 1


class TestTheFiledMatchRecord:
    def test_the_record_is_filed_beside_the_artifacts(self, tmp_path):
        """The four are projections, and a projection cannot be un-projected."""
        paths = write_artifacts(_summary(), tmp_path)

        assert json.loads(paths["record"].read_text(encoding="utf-8")) == _summary()

    def test_it_is_not_advertised_as_a_fifth_schema_artifact(self, tmp_path):
        paths = write_artifacts(_summary(), tmp_path)

        links = json.loads(paths["result"].read_text(encoding="utf-8"))["links"]
        assert "record" not in links

    def test_replaying_a_sub_game_corrects_the_series_rather_than_doubling_it(self, tmp_path):
        write_artifacts(_summary(steps=5), tmp_path)
        write_artifacts(_summary(steps=9), tmp_path)

        series = series_records(tmp_path / POLICE, _game_id())

        assert [record["steps"] for record in series] == [9]


class TestTheResultCoversTheWholeSeries:
    def test_a_later_sub_game_picks_its_siblings_up_from_disk(self, tmp_path):
        """A sub-game runs in its own process and only ever holds its own."""
        write_artifacts(_summary(sub_game=1), tmp_path)
        paths = write_artifacts(_summary(sub_game=2), tmp_path)

        result = json.loads(paths["result"].read_text(encoding="utf-8"))
        assert result["num_sub_games"] == 2

    def test_the_sub_games_are_ordered_by_number_not_by_the_directory(self, tmp_path):
        write_artifacts(_summary(sub_game=10), tmp_path)
        write_artifacts(_summary(sub_game=2), tmp_path)

        numbers = [record["step_zero"]["sub_game_number"] for record in _series(tmp_path)]
        assert numbers == [2, 10]

    def test_a_record_from_another_match_is_never_folded_in(self, tmp_path):
        """The exact mixing ch. 9.3.3 derives the filenames to prevent."""
        write_artifacts(_summary(), tmp_path)
        write_artifacts(_summary(opponent="someone-else"), tmp_path)

        assert len(_series(tmp_path)) == 1

    def test_an_unreadable_sibling_is_skipped_rather_than_raised_on(self, tmp_path):
        """Rule 35 costs both teams the match for a report that never arrived, and
        nothing at all for one that is short a sub-game."""
        write_artifacts(_summary(), tmp_path)
        (tmp_path / POLICE / f"record_{_game_id()}_g99.json").write_text("{half writ")

        assert len(_series(tmp_path)) == 1

    def test_a_directory_with_nothing_in_it_is_an_empty_series(self, tmp_path):
        assert series_records(tmp_path, _game_id()) == []


class TestWhatTheAgreedConfigContributes:
    def test_the_config_artifact_hashes_the_signed_file_when_one_is_loaded(self, tmp_path):
        config = config_with()

        paths = write_artifacts(_summary(), tmp_path, config)

        assert json.loads(paths["config"].read_text(encoding="utf-8"))["config"] == config.shared

    def test_the_result_is_scored_from_the_signed_table(self, tmp_path):
        paths = write_artifacts(_summary(), tmp_path, config_with())

        result = json.loads(paths["result"].read_text(encoding="utf-8"))
        assert result["sub_games"][0]["score"] == {POLICE: 20, THIEF: 5}

    def test_the_paths_are_derivable_without_writing_anything(self, tmp_path):
        """So a caller can say where a report will go before it exists."""
        paths = artifact_paths(tmp_path, facts_from(_summary()))

        assert not any(path.exists() for path in paths.values())


_SCHEMA_ARTIFACTS = ("declaration", "config", "log", "result")


def _game_id(opponent: str = THIEF) -> str:
    return game_id(POLICE, opponent)


def _series(base) -> list:
    return series_records(base / POLICE, _game_id())


def _summary(sub_game: int = 1, steps: int = 12, opponent: str = THIEF) -> dict:
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "steps": steps,
        "identity": {"group_id": POLICE, "github_commit": "a" * 40},
        "peer_identity": {"group_id": opponent, "github_commit": "b" * 40},
        "terms": {"board_size": 7, "num_games": 2},
        "step_zero": {"sub_game_number": sub_game},
        "started_at": "2026-08-05T09:00:00+00:00",
        "ended_at": "2026-08-05T09:02:00+00:00",
        "records": [],
        "tokens": {"tokens_total": 150},
        "audit": {"passed": True},
    }
