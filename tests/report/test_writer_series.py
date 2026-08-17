"""The result artifact across a whole series -- and across a rematch.

Split from test_writer.py to keep both files under the project's 150-line
rule; fixtures are defined there and imported here.
"""

import json

from police_agent.report.history import count_series
from police_agent.report.writer import series_records, write_artifacts
from tests.report.test_writer import POLICE, THIEF, _game_id, _summary


def _series(base) -> list:
    return series_records(base / POLICE, _game_id())


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


class TestRematchesAgainstTheSameOpponent:
    def test_a_rematch_after_a_completed_series_archives_the_old_one_first(self, tmp_path):
        """`game_id` has no clock in it, so a rematch's sub-game 1 would otherwise
        land on the first series' files -- not a replay to correct, a different
        match to keep."""
        write_artifacts(_summary(sub_game=1), tmp_path)
        write_artifacts(_summary(sub_game=2), tmp_path)  # series complete: 2/2 agreed

        write_artifacts(_summary(sub_game=1, steps=3), tmp_path)  # a rematch, later

        series = _series(tmp_path)
        assert [record["steps"] for record in series] == [3]

    def test_the_rematch_is_reflected_in_the_series_count(self, tmp_path):
        write_artifacts(_summary(sub_game=1), tmp_path, counted=True)
        write_artifacts(_summary(sub_game=2), tmp_path, counted=True)

        write_artifacts(_summary(sub_game=1, steps=3), tmp_path)

        assert count_series(tmp_path / POLICE, opponent_group_id=THIEF) == 1

    def test_an_in_progress_series_is_never_mistaken_for_a_rematch(self, tmp_path):
        """The existing crash-restart behaviour: replaying sub-game 1 before the
        series reached its agreed length corrects in place, same as always."""
        write_artifacts(_summary(sub_game=1, steps=5), tmp_path)

        write_artifacts(_summary(sub_game=1, steps=9), tmp_path)

        assert [record["steps"] for record in _series(tmp_path)] == [9]
        assert count_series(tmp_path / POLICE, opponent_group_id=THIEF) == 0
