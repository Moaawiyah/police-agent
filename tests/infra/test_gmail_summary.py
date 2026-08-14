"""`gmail_reporter` parses its own attachment and builds a matching subject and
body (`report/email_summary.py`), rather than mailing a data-free placeholder
alongside the real report -- see `tests/infra/test_gmail.py` for the low-level
`build_message` form tests this file does not repeat.
"""

import json
from email import message_from_bytes
from email.policy import default as default_policy

from police_agent.infra.gmail import draft_path, gmail_reporter
from tests.conftest import config_with


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


def _rich_report(tmp_path):
    path = tmp_path / "result_police-vs-thief.json"
    path.write_text(
        json.dumps(
            {
                "game_id": "police-vs-thief",
                "game_uid": "abc123",
                "num_sub_games": 2,
                "repositories": {
                    "MOAAMOHA": {"cop": "https://github.com/example/cop"},
                    "MOHAMOAA": {"thief": "https://github.com/example/thief"},
                },
                "final_result": {
                    "total_score": {"MOAAMOHA": 20, "MOHAMOAA": 5},
                    "winner_group": "MOAAMOHA",
                },
                "mutual_agreement": {"sha256": "deadbeef"},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_the_subject_matches_the_shared_uoh26_format(tmp_path):
    report = _rich_report(tmp_path)
    config = _enabled(game__group_id="MOAAMOHA")

    gmail_reporter(config, gate=_forbidden_gate())(report)

    assert _draft_of(report)["Subject"] == (
        "[UOH26 Final Game] police-vs-thief — MOAAMOHA result report"
    )


def test_the_body_carries_this_group_s_own_repository(tmp_path):
    """`repositories` is nested by group id; `own.group_id` must pick this
    peer's own entry back out rather than showing an empty line."""
    report = _rich_report(tmp_path)
    config = _enabled(game__group_id="MOAAMOHA", game__group_name="Team MOAAMOHA")

    gmail_reporter(config, gate=_forbidden_gate())(report)

    body = _draft_of(report).get_body().get_content()
    assert "Group: MOAAMOHA (Team MOAAMOHA)" in body
    assert "Winner: MOAAMOHA" in body
    assert "Cop repository:   https://github.com/example/cop" in body
    assert "Mutual agreement sha256: deadbeef" in body


def test_a_missing_group_id_degrades_to_the_same_placeholder_email_summary_uses(tmp_path):
    report = _rich_report(tmp_path)
    config = _enabled()  # no game.group_id override

    gmail_reporter(config, gate=_forbidden_gate())(report)

    assert "unknown-group" in _draft_of(report)["Subject"]
