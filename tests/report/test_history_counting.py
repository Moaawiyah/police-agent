"""Counting how many series are on record -- optionally against one opponent.

Split from test_history.py to keep both files under the project's 150-line
rule; fixtures are defined there and imported here.
"""

from datetime import UTC, datetime

from police_agent.report.history import archive_completed_series, count_series
from tests.report.test_history import THIEF, clock, facts, write_result


class TestCountingSeries:
    def test_no_ledger_is_zero_series(self, tmp_path):
        assert count_series(tmp_path) == 0

    def test_counts_every_archived_series(self, tmp_path):
        write_result(tmp_path, num_sub_games=2, agreed=2)
        archive_completed_series(tmp_path, facts(), now=clock)
        write_result(tmp_path, num_sub_games=1, agreed=1)
        archive_completed_series(tmp_path, facts(), now=lambda: datetime(2026, 8, 13, tzinfo=UTC))

        assert count_series(tmp_path) == 2

    def test_filters_by_opponent(self, tmp_path):
        write_result(tmp_path, num_sub_games=2, agreed=2)
        archive_completed_series(tmp_path, facts(), now=clock)

        assert count_series(tmp_path, opponent_group_id=THIEF) == 1
        assert count_series(tmp_path, opponent_group_id="someone-else") == 0

    def test_a_corrupt_ledger_counts_as_zero(self, tmp_path):
        (tmp_path / "series_history.json").write_text("{not a list")

        assert count_series(tmp_path) == 0
