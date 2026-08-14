"""The `--count` flag: a counted run mails the lecturer, cc'ing the team's own
`email.recipient`; an uncounted run must never reach the lecturer at all, even
by accident (`copthief-league-protocol` docs/WARNINGS.md §3).

Split out of `test_gmail.py` to keep both files under the project's line
budget.
"""

import json
from email import message_from_bytes

import pytest

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail import DEFAULTS, draft_path, gmail_reporter
from police_agent.infra.gmail_counted import recipients_for
from police_agent.shared.gatekeeper import Gatekeeper, GateLimits
from police_agent.shared.quota import DailyQuota
from tests.conftest import config_with
from tests.infra.fake_google import FakeGmail

LECTURER = DEFAULTS["recipient"]


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "result_police-vs-thief.json"
    path.write_text(json.dumps({"game_id": "police-vs-thief"}), encoding="utf-8")
    return path


class TestRecipientsFor:
    def test_uncounted_mails_the_configured_address_only(self):
        assert recipients_for("us@example.test", LECTURER, counted=False) == ("us@example.test", None)

    def test_counted_mails_the_lecturer_and_ccs_the_configured_address(self):
        assert recipients_for("us@example.test", LECTURER, counted=True) == (LECTURER, ["us@example.test"])

    def test_counted_does_not_cc_the_lecturer_to_itself(self):
        """`email.recipient` left at its shipped default already IS the
        lecturer -- a redundant cc would be a second copy of the same mail."""
        assert recipients_for(LECTURER, LECTURER, counted=True) == (LECTURER, None)

    def test_an_uncounted_run_refuses_the_lecturer_outright(self):
        """WARNINGS §3: an uncounted run owes nobody a report and must not
        accidentally spend the one meeting that counts (App. E rule 52)."""
        with pytest.raises(ConfigError, match="uncounted"):
            recipients_for(LECTURER, LECTURER, counted=False)

    def test_the_refusal_matches_case_and_whitespace_insensitively(self):
        """WARNINGS §3: 'matched case- and whitespace-insensitively' -- the
        exact wording, because a stray space or capital must not slip past it."""
        with pytest.raises(ConfigError):
            recipients_for(f"  {LECTURER.upper()}  ", LECTURER, counted=False)


class TestGmailReporterHonoursCount:
    def test_a_counted_draft_addresses_the_lecturer_and_ccs_the_team(self, report):
        config = _enabled(email__recipient="us@example.test")

        gmail_reporter(config, gate=_forbidden_gate(), counted=True)(report)

        drafted = message_from_bytes(draft_path(report).read_bytes())
        assert drafted["To"] == LECTURER
        assert drafted["Cc"] == "us@example.test"

    def test_an_uncounted_draft_still_only_addresses_the_team(self, report):
        config = _enabled(email__recipient="us@example.test")

        gmail_reporter(config, gate=_forbidden_gate(), counted=False)(report)

        drafted = message_from_bytes(draft_path(report).read_bytes())
        assert drafted["To"] == "us@example.test"
        assert drafted["Cc"] is None

    def test_an_uncounted_run_configured_at_the_lecturer_refuses_before_writing_anything(self, report):
        """The shipped default recipient IS the lecturer's address -- a team
        that never overrides `email.recipient` must not silently mail it."""
        config = _enabled()  # no recipient override: resolves to DEFAULTS

        with pytest.raises(ConfigError, match="uncounted"):
            gmail_reporter(config, gate=_forbidden_gate(), counted=False)(report)

        assert not draft_path(report).exists()

    def test_the_returned_note_names_both_recipients(self, monkeypatch, report, tmp_path):
        FakeGmail(monkeypatch)
        config = _enabled(
            email__recipient="us@example.test",
            email__mode="send",
            email__token_file=str(_token(tmp_path)),
        )

        note = gmail_reporter(config, gate=_gate(tmp_path), counted=True)(report)

        assert LECTURER in note
        assert "us@example.test" in note


def _enabled(**overrides):
    return config_with(**{"email__enabled": True, **overrides})


def _forbidden_gate():
    class Gate:
        def submit(self, call, budget=None):
            raise AssertionError("a draft must call nobody")

    return Gate()


def _token(tmp_path):
    token = tmp_path / "token.json"
    token.write_text('{"token": "stored"}', encoding="utf-8")
    return token


def _gate(tmp_path) -> Gatekeeper:
    return Gatekeeper(
        GateLimits(requests_per_minute=600), quota=DailyQuota(5, tmp_path / "quota.json")
    )
