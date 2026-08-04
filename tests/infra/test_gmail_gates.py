"""The send path: what it asks Google for, and what it has to get past first.

Nothing here reaches the network -- Google's libraries are an optional extra
imported lazily, so `tests/infra/fake_google.py` puts stand-ins under the names
those imports use and the real ones are never needed. That seam is also the
feature: a machine with no Google account installed can still run the suite.

Two things are being defended. The consent flow must ask for exactly the scope
rule 30 allows and must not repeat itself once a token exists; and every real
send must cross ch. 9.3.1's gates, because an agent that mailed straight past
them is the one that gets the reporting account suspended.
"""

import json
import sys

import pytest

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail import SCOPE, api_body, build_message, gmail_reporter
from police_agent.infra.gmail_client import credentials, send_raw
from police_agent.shared.gatekeeper import Gatekeeper, GateLimits, QuotaExceededError
from police_agent.shared.quota import DailyQuota
from tests.conftest import config_with
from tests.infra.fake_google import FakeGmail


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "result_police-vs-thief.json"
    path.write_text(json.dumps({"game_id": "police-vs-thief"}), encoding="utf-8")
    return path


class TestWhatGoogleIsAskedFor:
    def test_the_message_is_handed_over_whole_and_encoded(self, monkeypatch, report, tmp_path):
        google = FakeGmail(monkeypatch)
        message = build_message("them@example.test", "subject", report)

        identifier = send_raw(api_body(message), tmp_path / "creds.json", _token(tmp_path))

        assert identifier == "msg-1"
        assert google.sent[0]["userId"] == "me"
        assert google.sent[0]["body"] == api_body(message)

    def test_it_asks_the_gmail_v1_service(self, monkeypatch, report, tmp_path):
        google = FakeGmail(monkeypatch)

        send_raw({"raw": "x"}, tmp_path / "creds.json", _token(tmp_path))

        assert google.built[:2] == ("gmail", "v1")


class TestTheConsentFlow:
    def test_a_stored_token_is_reused_rather_than_consented_to_again(self, monkeypatch, tmp_path):
        google = FakeGmail(monkeypatch)

        credentials(tmp_path / "creds.json", _token(tmp_path))

        assert google.consented == 0

    def test_the_scope_requested_is_exactly_the_one_rule_thirty_allows(self, monkeypatch, tmp_path):
        google = FakeGmail(monkeypatch)

        credentials(tmp_path / "creds.json", _token(tmp_path))

        assert google.scopes == [[SCOPE]]

    def test_an_expired_token_is_refreshed_not_re_consented(self, monkeypatch, tmp_path):
        google = FakeGmail(monkeypatch, valid=False)

        credentials(tmp_path / "creds.json", _token(tmp_path))

        assert (google.refreshed, google.consented) == (1, 0)

    def test_the_first_run_consents_and_stores_the_token(self, monkeypatch, tmp_path):
        """Interactive, and deliberately not attempted mid-match: a run that needs
        it is a run a human is watching, which is why enabled defaults to false."""
        google = FakeGmail(monkeypatch)
        secrets = tmp_path / "creds.json"
        secrets.write_text("{}", encoding="utf-8")
        token = tmp_path / "token.json"

        credentials(secrets, token)

        assert google.consented == 1
        assert token.read_text(encoding="utf-8") == '{"token": "stored"}'

    def test_missing_client_secrets_are_named_with_where_to_get_them(self, monkeypatch, tmp_path):
        FakeGmail(monkeypatch)

        with pytest.raises(ConfigError, match="Google Cloud console"):
            credentials(tmp_path / "nowhere.json", tmp_path / "token.json")

    def test_the_absent_optional_extra_is_named_rather_than_raised_as_a_traceback(
        self, monkeypatch, tmp_path
    ):
        """A setup problem with a one-line fix, not a bug."""
        monkeypatch.setitem(sys.modules, "google.oauth2.credentials", None)

        with pytest.raises(ConfigError, match=r"police-agent\[gmail\]"):
            credentials(tmp_path / "creds.json", tmp_path / "token.json")

    def test_an_absent_client_library_is_named_too(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "googleapiclient.discovery", None)

        with pytest.raises(ConfigError, match=r"police-agent\[gmail\]"):
            send_raw({"raw": "x"}, tmp_path / "creds.json", tmp_path / "token.json")


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
