"""What Google is asked for, and the consent flow, split out of
test_gmail_gates.py to keep both files under the project's line budget.

Two things are being defended: the consent flow must ask for exactly the
scope rule 30 allows and must not repeat itself once a token exists.
"""

import json
import sys

import pytest

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail import SCOPE, api_body, build_message
from police_agent.infra.gmail_client import credentials, send_raw
from tests.infra.fake_google import FakeGmail
from tests.infra.test_gmail_gates import _token


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

    def test_a_revoked_grant_is_named_with_its_fix_rather_than_a_raw_refresh_error(
        self, monkeypatch, tmp_path
    ):
        """The 7-day expiry of a 'Testing' consent screen ends a series with an
        opaque `RefreshError` banner after every sub-game has already been
        played. What the operator needs is the one-line fix, not the traceback --
        and re-consenting silently would open a browser mid-match."""
        FakeGmail(monkeypatch, valid=False, revoked=True)

        with pytest.raises(ConfigError, match="invalid_grant"):
            credentials(tmp_path / "creds.json", _token(tmp_path))

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
