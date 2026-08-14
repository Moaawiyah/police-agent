"""The mandatory report as mail: an attachment, a matching summary, off by default.

Rule 35 makes this the most expensive thing in the repository to get wrong -- no
report means no points for *either* team. Rule 34 fixes the attachment's form
(structured, machine-readable JSON); the body is a human-readable summary of
that same JSON (`report/email_summary.py`), not a substitute for it -- the
settled cross-team convention this project follows.

Every test that could touch the network proves it did not: the default path is
handed a gate that raises if anything is submitted to it.
"""

import base64
import json
from email import message_from_bytes
from email.policy import default as default_policy

import pytest

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail import (
    DEFAULTS,
    SCOPE,
    api_body,
    build_message,
    draft_path,
    gmail_reporter,
    settings,
)
from tests.conftest import config_with


@pytest.fixture
def report(tmp_path):
    """A result artifact on disk, which is the only thing that gets mailed."""
    path = tmp_path / "result_police-vs-thief.json"
    path.write_text(json.dumps({"game_id": "police-vs-thief"}), encoding="utf-8")
    return path


class TestTheFormRuleThirtyFourFixes:
    def test_the_report_is_an_attachment(self, report):
        message = build_message("them@example.test", "subject", report)

        attached = list(message.iter_attachments())
        assert len(attached) == 1
        assert attached[0].get_content_type() == "application/json"

    def test_the_attachment_is_the_report_byte_for_byte(self, report):
        message = build_message("them@example.test", "subject", report)

        attached = next(message.iter_attachments())
        assert attached.get_payload(decode=True) == report.read_bytes()
        assert attached.get_filename() == report.name

    def test_a_default_body_still_points_at_the_attachment(self, report):
        """No summary given: falls back to a one-line pointer, not an empty body."""
        body = build_message("them@example.test", "subject", report).get_body().get_content()

        assert "attached" in body.lower()

    def test_the_api_body_is_the_whole_message_base64url_encoded(self, report):
        message = build_message("them@example.test", "subject", report)

        rebuilt = message_from_bytes(_decode(api_body(message)["raw"]), policy=default_policy)

        assert rebuilt["To"] == "them@example.test"
        assert len(list(rebuilt.iter_attachments())) == 1


class TestTheScopeRuleThirtyFixes:
    def test_it_is_exactly_send(self):
        """Never widen it: compose or modify would let a stray call touch mail
        this agent has no business touching."""
        assert SCOPE == "https://www.googleapis.com/auth/gmail.send"

    def test_the_shipped_recipient_is_the_lecturers_reporting_address(self):
        assert DEFAULTS["recipient"] == "rmisegal+uoh26finalgame@gmail.com"


class TestOffAndInertByDefault:
    def test_reporting_is_switched_off_in_the_shipped_settings(self, report):
        """A practice match must not mail anybody."""
        assert gmail_reporter(config_with(), gate=_forbidden_gate())(report) is None

    def test_a_draft_is_a_local_file_and_calls_nobody(self, report):
        """`gmail.send` cannot create a Gmail draft -- rule 30 wins over convenience."""
        note = gmail_reporter(_enabled(), gate=_forbidden_gate())(report)

        assert draft_path(report).is_file()
        assert str(draft_path(report)) in note

    def test_the_draft_carries_the_attachment_a_send_would_have(self, report):
        gmail_reporter(_enabled(), gate=_forbidden_gate())(report)

        drafted = _draft_of(report)
        assert next(drafted.iter_attachments()).get_payload(decode=True) == report.read_bytes()

    def test_the_draft_lands_beside_the_report_it_carries(self, report):
        assert draft_path(report) == report.with_name(f"draft_{report.stem}.eml")

    def test_it_builds_its_own_gate_when_the_caller_supplies_none(self, report, tmp_path):
        """Rule 28: its own `Gatekeeper` rather than the runtime's -- figure 13's
        gates protect a provider's allowance, and Ollama's rate window is not Google's."""
        reporter = gmail_reporter(_enabled(email__quota_file=str(tmp_path / "quota.json")))

        assert reporter(report)  # the draft path calls nobody, and still built one

    def test_a_mode_nobody_recognises_is_named_rather_than_guessed(self, report):
        reporter = gmail_reporter(_enabled(email__mode="post"), gate=_forbidden_gate())

        with pytest.raises(ConfigError, match="post"):
            reporter(report)


class TestReadingTheEmailBlock:
    def test_the_shipped_defaults_stand_in_for_every_absent_key(self):
        assert settings() == DEFAULTS

    def test_a_configured_value_wins(self):
        config = _enabled(email__recipient="me@example.test")
        assert settings(config)["recipient"] == "me@example.test"

    def test_a_false_setting_is_not_mistaken_for_an_absent_one(self):
        """`or` would read `enabled = false` as "unset" and turn mailing back on."""
        assert settings(_enabled(email__enabled=False))["enabled"] is False


def _enabled(**overrides):
    # Non-lecturer default: an uncounted send now refuses that address (WARNINGS §3).
    overrides.setdefault("email__recipient", "them@example.test")
    overrides.setdefault("email__enabled", True)
    return config_with(**overrides)


def _forbidden_gate():
    class Gate:
        def submit(self, call, budget=None):
            raise AssertionError("the offline path reached for the network")

    return Gate()


def _draft_of(report):
    return message_from_bytes(draft_path(report).read_bytes(), policy=default_policy)


def _decode(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw)
