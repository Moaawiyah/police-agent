"""The daily allowance itself: booking calls, rolling over, surviving a restart.

Two things are being defended. The first is that the count survives a restart:
a sub-game is its own process, so a counter that lived in memory would report a
series of twenty sends as one and the provider would disagree at the worst
possible moment. The second is ordering -- the quota is the *first* gate, so a
day that is already spent costs no queueing, no token and no socket (see
`test_quota_gate.py`, split out to keep both files under the line budget, for
the Gatekeeper side of that).

The clock is injected rather than mocked at the module, so "tomorrow" is a value
a test passes in and no test waits for midnight.
"""

import json
from datetime import UTC, datetime

import pytest

from police_agent.shared.gatekeeper import QuotaExceededError
from police_agent.shared.quota import DailyQuota

TODAY, TOMORROW = "2026-08-05", "2026-08-06"


def quota(limit: int = 3, path=None, day: str = TODAY) -> DailyQuota:
    """An allowance on a clock the test owns."""
    return DailyQuota(limit, path, today=lambda: day)


class TestTheAllowance:
    def test_calls_are_booked_against_today(self):
        allowance = quota()

        allowance.spend()
        allowance.spend()

        assert allowance.remaining == 1

    def test_the_call_past_the_limit_is_refused(self):
        allowance = quota(limit=1)
        allowance.spend()

        with pytest.raises(QuotaExceededError, match="1/1"):
            allowance.spend()

    def test_a_refused_call_does_not_quietly_consume_the_allowance(self):
        """Refused before spending, so a caller turned away has spent nothing."""
        allowance = quota(limit=2)

        with pytest.raises(QuotaExceededError):
            allowance.spend(cost=3)

        assert allowance.remaining == 2

    def test_the_message_says_when_the_allowance_comes_back(self):
        allowance = quota(limit=0)

        with pytest.raises(QuotaExceededError, match="midnight UTC"):
            allowance.spend()

    def test_the_snapshot_is_the_evidence_the_first_gate_was_there(self):
        allowance = quota()
        allowance.spend()

        assert allowance.snapshot() == {"date": TODAY, "spent": 1, "limit": 3}

    def test_the_shipped_clock_is_the_utc_date(self):
        """Local time would grant a second allowance to a laptop that flew west."""
        assert DailyQuota(1).snapshot()["date"] == datetime.now(UTC).date().isoformat()


class TestTheDayRollingOver:
    def test_a_new_day_is_a_fresh_allowance(self):
        day = [TODAY]
        allowance = DailyQuota(1, today=lambda: day[0])
        allowance.spend()

        day[0] = TOMORROW

        assert allowance.remaining == 1

    def test_it_is_noticed_on_use_rather_than_on_a_timer(self):
        """There is no scheduler in this process to hang a reset on."""
        day = [TODAY]
        allowance = DailyQuota(1, today=lambda: day[0])
        allowance.spend()
        day[0] = TOMORROW

        allowance.spend()  # would raise if the rollover needed a tick

        assert allowance.snapshot() == {"date": TOMORROW, "spent": 1, "limit": 1}


class TestSurvivingARestart:
    def test_the_count_is_remembered_across_processes(self, tmp_path):
        """A sub-game is its own process; an in-memory counter would forget."""
        ledger = tmp_path / "mail.json"
        quota(path=ledger).spend()
        quota(path=ledger).spend()

        assert quota(path=ledger).remaining == 1

    def test_yesterdays_ledger_does_not_hold_todays_calls_against_us(self, tmp_path):
        ledger = tmp_path / "mail.json"
        quota(path=ledger, day=TODAY).spend()

        assert quota(path=ledger, day=TOMORROW).remaining == 3

    def test_the_ledger_is_created_with_its_directory(self, tmp_path):
        ledger = tmp_path / "nested" / "mail.json"

        quota(path=ledger).spend()

        assert json.loads(ledger.read_text(encoding="utf-8")) == {"date": TODAY, "count": 1}

    def test_an_unreadable_ledger_is_an_empty_day_not_a_refusal(self, tmp_path):
        """A damaged local file must not become rule 35's 'no report at all'."""
        ledger = tmp_path / "mail.json"
        ledger.write_text("{half writ", encoding="utf-8")

        assert quota(path=ledger).remaining == 3

    def test_a_ledger_that_cannot_be_written_does_not_abandon_the_send(self, tmp_path):
        """Worse accounting, not a lost report."""
        blocked = tmp_path / "mail.json"
        blocked.mkdir()  # a directory where the ledger wants to be

        quota(path=blocked).spend()  # must not raise
