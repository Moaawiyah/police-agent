"""The CLI's `--report` flag, and the GUI/team_sync paths that feed it,
split out of test_reporting.py to keep both files under the project's line
budget. See that file's docstring for why the reporting chain must be
reachable at every layer, not just from `report/writer.py` directly.
"""

from police_agent import __main__ as cli
from police_agent.sdk import DEFAULT_REPORT_DIR


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


class TestTheGuiReportsTheWholeSeries:
    """The GUI's Start button always plays the whole agreed series
    (gui/player.py), never one sub-game -- so `--gui --report` must write
    every sub-game it played, the same way headless `--series --report`
    already does, and not just the last one (see `__main__._finish_series`,
    the writer both paths now share)."""

    def test_report_writes_every_sub_game_the_gui_played(self, monkeypatch):
        agent = _StubAgent()
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)
        monkeypatch.setattr(cli, "_play_with_window", lambda _agent: _two_sub_games())

        cli.main(["--gui", "--report"])

        assert agent.reported == [DEFAULT_REPORT_DIR, DEFAULT_REPORT_DIR]

    def test_a_gui_run_that_played_nothing_reports_nothing(self, monkeypatch, capsys):
        agent = _StubAgent()
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)
        monkeypatch.setattr(cli, "_play_with_window", lambda _agent: [])

        cli.main(["--gui", "--report"])

        assert agent.reported == []
        assert "no match played" in capsys.readouterr().out

    def test_report_is_a_noop_under_team_sync(self, monkeypatch, capsys):
        """team_sync's own coordinator already wrote artifacts and mailed once as
        each sub-game settled (team_sync/scheduler.py); `_report_series` has no
        idempotency check of its own, so calling it here too would re-send the
        same email. `--report` must become a no-op rather than double-mail."""
        agent = _StubAgent(team_sync_enabled=True)
        monkeypatch.setattr(cli, "PoliceAgentSDK", lambda options: agent)
        monkeypatch.setattr(cli, "_play_series_headless", lambda _agent: _two_sub_games())

        cli.main(["--series", "--report"])

        assert agent.reported == []
        assert "no-op under team_sync" in capsys.readouterr().err


def _two_sub_games() -> list[dict]:
    return [
        {"result": "capture", "winner": "police", "steps": 12},
        {"result": "survival", "winner": "thief", "steps": 35},
    ]


class _StubConfig:
    """Just enough of the real config surface for `_finish_series`'s team_sync check."""

    def __init__(self, team_sync_enabled: bool = False) -> None:
        self._team_sync_enabled = team_sync_enabled

    def get(self, key, default=None):
        if key == "team_sync.enabled":
            return self._team_sync_enabled
        return default


class _StubAgent:
    """The SDK's reporting surface only, so the CLI test opens no socket."""

    host, port, opponent_url, public_url = "127.0.0.1", 8801, "http://elsewhere/mcp", None

    def __init__(self, mailed: str | None = None, team_sync_enabled: bool = False) -> None:
        self.reported: list[str] = []
        self.mailed = mailed
        self.config = _StubConfig(team_sync_enabled)

    def connect(self) -> None:
        return None

    def play(self) -> dict:
        return {"result": "capture", "winner": "police", "steps": 1}

    def write_artifacts(self, summary: dict, base) -> dict:
        self.reported.append(str(base))
        return {"result": f"{base}/result.json"}

    def email_report(self, paths: dict) -> str | None:
        return self.mailed
