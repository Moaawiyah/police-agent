"""Every real send crosses ch. 9.3.1's gates, because an agent that mailed
straight past them is the one that gets the reporting account suspended.

Nothing here reaches the network -- Google's libraries are an optional extra
imported lazily, so `tests/infra/fake_google.py` puts stand-ins under the names
those imports use and the real ones are never needed. That seam is also the
feature: a machine with no Google account installed can still run the suite.

What Google is asked for, and the consent flow, live in
`test_gmail_consent.py`, split out to keep both files under the project's
line budget.
"""

import json

import pytest

from police_agent.infra.gmail import gmail_reporter
from police_agent.shared.gatekeeper import Gatekeeper, GateLimits, QuotaExceededError
from police_agent.shared.quota import DailyQuota
from tests.conftest import config_with
from tests.infra.fake_google import FakeGmail


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "result_police-vs-thief.json"
    path.write_text(json.dumps({"game_id": "police-vs-thief"}), encoding="utf-8")
    return path


class TestEveryRealSendCrossesTheGates:
    def test_the_send_goes_through_the_gatekeeper(self, monkeypatch, report, tmp_path):
        """An agent that mailed straight past it is the one that gets suspended."""
        FakeGmail(monkeypatch)
        gate = _gate(tmp_path)

        _sender(tmp_path, gate)(report)

        assert gate.snapshot()["sent"] == 1

    def test_it_spends_the_days_allowance(self, monkeypatch, report, tmp_path):
        FakeGmail(monkeypatch)
        gate = _gate(tmp_path, limit=2)

        _sender(tmp_path, gate)(report)

        assert gate.snapshot()["quota"]["spent"] == 1

    def test_a_spent_day_refuses_before_google_is_called_at_all(
        self, monkeypatch, report, tmp_path
    ):
        google = FakeGmail(monkeypatch)
        gate = _gate(tmp_path, limit=0)

        with pytest.raises(QuotaExceededError):
            _sender(tmp_path, gate)(report)

        assert google.sent == []

    def test_the_sentence_it_returns_says_where_the_report_went(
        self, monkeypatch, report, tmp_path
    ):
        """The one failure rule 35 punishes is a report nobody noticed was unsent."""
        FakeGmail(monkeypatch)

        note = _sender(tmp_path, _gate(tmp_path))(report)

        assert "them@example.test" in note
        assert "msg-1" in note


def _token(tmp_path):
    token = tmp_path / "token.json"
    token.write_text('{"token": "stored"}', encoding="utf-8")
    return token


def _gate(tmp_path, limit: int = 5) -> Gatekeeper:
    return Gatekeeper(
        GateLimits(requests_per_minute=600),
        quota=DailyQuota(limit, tmp_path / "quota.json"),
    )


def _sender(tmp_path, gate):
    """A reporter configured to really send, against the faked client."""
    return gmail_reporter(
        config_with(
            email__enabled=True,
            email__mode="send",
            email__recipient="them@example.test",
            email__token_file=str(_token(tmp_path)),
        ),
        gate=gate,
    )
