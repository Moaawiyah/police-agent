"""Closing an `NgrokTunnel`, and the bare agent-API helpers it's built on,
split out of test_tunnel.py to keep both files under the project's line
budget. See test_tunnel.py's docstring for why ngrok is faked whole.
"""

import io
import urllib.error
from pathlib import Path

from police_agent.infra.ngrok_agent import _agent_tunnels, _tail
from police_agent.infra.tunnel import NgrokTunnel
from tests.infra.fake_ngrok import PUBLIC, FakeProcess


def test_closing_stops_the_agent_and_takes_its_log_with_it(tmp_path):
    # Until it stops, it is still holding the reserved domain.
    process, log = FakeProcess(), tmp_path / "ngrok.log"
    log.write_text("...", encoding="utf-8")

    NgrokTunnel(PUBLIC, process, log).close()

    assert process.terminated and not log.exists()


def test_closing_twice_stops_it_once():
    """atexit files a close of its own, so a second one always happens."""
    process = FakeProcess()
    tunnel = NgrokTunnel(PUBLIC, process)

    tunnel.close()
    process.terminated = False
    tunnel.close()

    assert not process.terminated


def test_an_agent_that_ignores_terminate_is_killed():
    process = FakeProcess(deaf=True)

    NgrokTunnel(PUBLIC, process).close()

    assert process.killed


def test_an_agent_api_that_is_not_there_reports_no_tunnels(monkeypatch):
    # The usual case: ngrok is not running, and nothing about that is an error.
    def refused(url, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", refused)

    assert _agent_tunnels() == []


def test_an_answer_that_carries_no_tunnel_list_is_ignored(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=None: io.BytesIO(b"{}"))

    assert _agent_tunnels() == []


def test_a_log_that_vanished_explains_nothing_rather_than_crashing():
    assert _tail(Path("/nowhere/ngrok.log")) == ""
