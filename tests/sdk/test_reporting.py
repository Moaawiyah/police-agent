"""Reporting reached the way a front end reaches it: through the SDK.

The artifacts themselves are tested in `tests/report/`. What is at stake here
is that the mandatory reporting chain is actually *reachable* -- the
submission guidelines require every capability to be available through the
SDK layer, and a report that only `report/writer.py` knew how to produce
would be a capability this agent does not really have.

The CLI's `--report` flag (and the GUI/team_sync paths that feed it) is
tested in `test_reporting_cli.py`, split out to keep both files under the
project's line budget.
"""

import json

from police_agent.infra.gmail import draft_path
from police_agent.sdk import DEFAULT_REPORT_DIR, PoliceAgentSDK
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn

GROUP = "unknown-group"  # game.json carries no identity; game.toml does


class TestTheSdkWritesTheReport:
    def test_a_played_match_becomes_four_artifacts_on_disk(self, tmp_path):
        agent = _agent()

        paths = agent.write_artifacts(agent.play(), tmp_path)

        assert set(paths) >= {"declaration", "config", "log", "result"}
        assert all(path.exists() for path in paths.values())

    def test_the_agreed_terms_reach_the_config_artifact(self, tmp_path):
        """The SDK holds the loaded config; the writer would otherwise fall back
        to the handshake subset and hash something narrower than the signed file."""
        agent = _agent()

        paths = agent.write_artifacts(agent.play(), tmp_path)

        config = json.loads(paths["config"].read_text(encoding="utf-8"))
        assert config["config"] == agent.config.shared

    def test_the_declaration_reports_the_machine_the_match_was_played_on(self, tmp_path):
        """Rule 24 end to end: probed, sealed before the first move, published."""
        agent = _agent()

        paths = agent.write_artifacts(agent.play(), tmp_path)

        declaration = json.loads(paths["declaration"].read_text(encoding="utf-8"))
        assert declaration["groups"]["group_1"]["hardware_spec"]["cpu_type"] == "Test CPU"

    def test_the_result_carries_the_commit_that_was_played(self, tmp_path):
        """Rule 53: the revision the grader has to be able to check out."""
        agent = _agent()

        paths = agent.write_artifacts(agent.play(), tmp_path)

        result = json.loads(paths["result"].read_text(encoding="utf-8"))
        assert result["sub_games"][0]["github_commit"][GROUP] == "0" * 40

    def test_the_default_directory_is_named_rather_than_spelled_out_twice(self):
        assert DEFAULT_REPORT_DIR == "logs"


class TestTheSdkMailsTheReport:
    def test_a_default_run_mails_nobody(self, tmp_path):
        """`email.enabled` is false in the shipped settings: a practice match must
        not report itself to the lecturer."""
        agent = _agent()

        assert agent.email_report(agent.write_artifacts(agent.play(), tmp_path)) is None

    def test_the_result_is_the_artifact_that_gets_sent(self, tmp_path):
        """Picked here so no caller can mail the wrong one of the four."""
        agent = _agent(email__enabled=True, email__quota_file=str(tmp_path / "quota.json"))
        paths = agent.write_artifacts(agent.play(), tmp_path)

        note = agent.email_report(paths)

        assert str(draft_path(paths["result"])) in note
        assert draft_path(paths["result"]).is_file()

    def test_nothing_is_mailed_when_no_report_was_written(self):
        assert _agent().email_report({}) is None


def _agent(**overrides) -> PoliceAgentSDK:
    return PoliceAgentSDK(
        config=config_with(**overrides), transport=FakeTransport(incoming=[thief_turn(1)])
    )
