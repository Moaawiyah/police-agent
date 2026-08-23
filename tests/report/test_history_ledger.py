"""The series_history.json ledger entry archiving writes.

Split from test_history.py to keep both files under the project's 150-line
rule; fixtures are defined there and imported here.
"""

import json

from police_agent.report.history import archive_completed_series
from tests.report.test_history import CLOCK, GAME_ID, POLICE, THIEF, clock, facts, write_result


class TestTheLedgerEntry:
    def test_archiving_appends_one_ledger_entry(self, tmp_path):
        write_result(
            tmp_path,
            num_sub_games=2,
            agreed=2,
            game_uid="the-uid",
            game_started_at="2026-08-01T09:00:00+00:00",
            game_ended_at="2026-08-01T09:10:00+00:00",
            final_result={"winner_group": POLICE},
            counted=True,
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
                "counted": True,
            }
        ]

    def test_a_warm_up_is_archived_but_not_marked_counted(self, tmp_path):
        """`--count` was never passed, so the ledger entry says so -- and
        count_series must not fold it into the tally."""
        write_result(tmp_path, num_sub_games=2, agreed=2)

        archive_completed_series(tmp_path, facts(), now=clock)

        entries = json.loads((tmp_path / "series_history.json").read_text())
        assert entries[0]["counted"] is False
