"""Reporting reached the way a front end reaches it: through the SDK, then the CLI.

The artifacts themselves are tested in `tests/report/`. What is at stake here is
that the mandatory reporting chain is actually *reachable* -- the submission
guidelines require every capability to be available through the SDK layer, and a
report that only `report/writer.py` knew how to produce would be a capability
this agent does not really have.
"""

import json

from police_agent import __main__ as cli
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
        assert result["sub_games"][0]["github_commits"][GROUP] == "0" * 40

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


class TestTheCliFlag:
    def test_report_writes_the_artifacts_where_the_flag_says(self, tmp_path, monkeypatch):
        agent = _StubAgent()
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)

        assert cli.main(["--report", "--report-dir", str(tmp_path)]) == 0
        assert agent.reported == [str(tmp_path)]

    def test_a_run_without_the_flag_writes_nothing(self, tmp_path, monkeypatch):
        """A practice match should not file a league report."""
        agent = _StubAgent()
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)

        cli.main([])

        assert agent.reported == []

    def test_the_flag_defaults_to_the_sdks_directory(self, monkeypatch):
        agent = _StubAgent()
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)

        cli.main(["--report"])

        assert agent.reported == [DEFAULT_REPORT_DIR]

    def test_it_says_so_when_mailing_is_switched_off(self, monkeypatch, capsys):
        """Silence would read exactly like a report that was sent -- rule 35's
        one failure mode is a report nobody noticed never went."""
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: _StubAgent())

        cli.main(["--report"])

        assert "email reporting is off" in capsys.readouterr().err

    def test_it_prints_where_a_sent_report_went(self, monkeypatch, capsys):
        agent = _StubAgent(mailed="sent to them@example.test as message msg-1")
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)

        cli.main(["--report"])

        assert "msg-1" in capsys.readouterr().err


class _StubAgent:
    """The SDK's reporting surface only, so the CLI test opens no socket."""

    host, port, opponent_url, public_url = "127.0.0.1", 8801, "http://elsewhere/mcp", None

    def __init__(self, mailed: str | None = None) -> None:
        self.reported: list[str] = []
        self.mailed = mailed

    def connect(self) -> None:
        return None

    def play(self) -> dict:
        return {"result": "capture", "winner": "police", "steps": 1}

    def write_artifacts(self, summary: dict, base) -> dict:
        self.reported.append(str(base))
        return {"result": f"{base}/result.json"}

    def email_report(self, paths: dict) -> str | None:
        return self.mailed


def _agent(**overrides) -> PoliceAgentSDK:
    return PoliceAgentSDK(
        config=config_with(**overrides), transport=FakeTransport(incoming=[thief_turn(1)])
    )
