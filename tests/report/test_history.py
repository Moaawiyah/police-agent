"""Archiving a finished series before a rematch overwrites it.

`history.py`'s core job: move a completed series' files aside before a fresh
sub-game 1 for the same opponent lands on them. Counting the resulting
ledger is covered separately in test_history_counting.py (150-line rule).
"""

import json
from datetime import UTC, datetime

from police_agent.report.facts import ReportFacts
from police_agent.report.history import archive_completed_series

POLICE, THIEF = "police-team", "thief-team"
GAME_ID = f"{POLICE}-vs-{THIEF}"
CLOCK = datetime(2026, 8, 12, 18, 0, 0, tzinfo=UTC)


class TestASeriesStillInProgress:
    def test_a_missing_result_is_nothing_to_archive(self, tmp_path):
        assert archive_completed_series(tmp_path, facts(), now=clock) is False
        assert not (tmp_path / "archive").exists()

    def test_a_short_result_is_left_alone(self, tmp_path):
        write_result(tmp_path, num_sub_games=1, agreed=2)

        assert archive_completed_series(tmp_path, facts(), now=clock) is False
        assert (tmp_path / f"result_{GAME_ID}.json").is_file()

    def test_a_corrupt_result_is_left_alone_not_guessed_at(self, tmp_path):
        (tmp_path / f"result_{GAME_ID}.json").write_text("{not json")

        assert archive_completed_series(tmp_path, facts(), now=clock) is False
        assert (tmp_path / f"result_{GAME_ID}.json").is_file()


class TestArchivingAFinishedSeries:
    def test_a_complete_result_is_archived(self, tmp_path):
        write_result(tmp_path, num_sub_games=2, agreed=2)

        moved = archive_completed_series(tmp_path, facts(), now=clock)

        assert moved is True
        assert not (tmp_path / f"result_{GAME_ID}.json").exists()

    def test_the_archived_files_land_together_under_one_folder(self, tmp_path):
        write_result(tmp_path, num_sub_games=2, agreed=2)
        (tmp_path / f"declaration_{GAME_ID}.json").write_text("{}")
        (tmp_path / f"config_{GAME_ID}_g01.json").write_text("{}")
        (tmp_path / f"record_{GAME_ID}_g01.json").write_text("{}")

        archive_completed_series(tmp_path, facts(), now=clock)

        destination = tmp_path / "archive" / f"20260812T180000Z_{GAME_ID}"
        names = {path.name for path in destination.iterdir()}
        assert names == {
            f"result_{GAME_ID}.json",
            f"declaration_{GAME_ID}.json",
            f"config_{GAME_ID}_g01.json",
            f"record_{GAME_ID}_g01.json",
        }

    def test_a_stray_file_from_a_colliding_game_id_is_left_alone(self, tmp_path):
        """`<a>-vs-<b>` must not sweep up `<a>-vs-<b>b`'s files as a substring match."""
        write_result(tmp_path, num_sub_games=2, agreed=2)
        colliding = tmp_path / f"record_{GAME_ID}extra_g01.json"
        colliding.write_text("{}")

        archive_completed_series(tmp_path, facts(), now=clock)

        assert colliding.is_file()

    def test_archiving_appends_one_ledger_entry(self, tmp_path):
        write_result(
            tmp_path,
            num_sub_games=2,
            agreed=2,
            game_uid="the-uid",
            game_started_at="2026-08-01T09:00:00+00:00",
            game_ended_at="2026-08-01T09:10:00+00:00",
            final_result={"winner_group": POLICE},
        )

        archive_completed_series(tmp_path, facts(), now=clock)

        entries = json.loads((tmp_path / "series_history.json").read_text())
        assert entries == [
            {
                "game_id": GAME_ID,
                "game_uid": "the-uid",
                "opponent_group_id": THIEF,
                "own_group_id": POLICE,
                "num_sub_games": 2,
                "final_result": {"winner_group": POLICE},
                "started_at": "2026-08-01T09:00:00+00:00",
                "ended_at": "2026-08-01T09:10:00+00:00",
                "archived_at": CLOCK.isoformat(),
            }
        ]

    def test_archiving_leaves_the_directory_clean_for_the_next_series(self, tmp_path):
        write_result(tmp_path, num_sub_games=2, agreed=2)
        (tmp_path / f"declaration_{GAME_ID}.json").write_text("{}")

        archive_completed_series(tmp_path, facts(), now=clock)

        remaining = [path for path in tmp_path.glob(f"*{GAME_ID}*") if path.is_file()]
        assert remaining == []


class TestResilience:
    def test_an_archive_that_cannot_be_written_does_not_raise(self, tmp_path):
        """A file sitting where the archive folder needs to go blocks `mkdir`."""
        write_result(tmp_path, num_sub_games=2, agreed=2)
        (tmp_path / "archive").write_text("not a directory")

        moved = archive_completed_series(tmp_path, facts(), now=clock)

        assert moved is False
        assert (tmp_path / f"result_{GAME_ID}.json").is_file()


def clock() -> datetime:
    return CLOCK


def facts(opponent: str = THIEF) -> ReportFacts:
    return ReportFacts(
        game_id=f"{POLICE}-vs-{opponent}",
        game_uid="new-uid",
        own_group_id=POLICE,
        opponent_group_id=opponent,
        sub_game_number=1,
        started_at="2026-08-12T18:00:00+00:00",
        ended_at="",
        num_sub_games=2,
        token_budget=0,
    )


def write_result(directory, num_sub_games: int, agreed: int, **extra) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = {"num_sub_games": num_sub_games, "num_sub_games_agreed": agreed, **extra}
    (directory / f"result_{GAME_ID}.json").write_text(json.dumps(body))
