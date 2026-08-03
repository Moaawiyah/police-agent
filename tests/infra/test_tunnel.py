"""The ngrok tunnel, with nothing installed and no packet leaving the machine.

One branch here is a tunnel coming up; every other is a way a league match
cannot be played at all (Appendix He rule 10), so ngrok is faked whole -- the
binary, the child process, the agent API -- rather than its failure paths being
left to a manual check nobody performs on the morning of a match.
"""

import io
import json
import subprocess
import urllib.error
from pathlib import Path

import pytest

from police_agent.exceptions import ConfigError, TransportError
from police_agent.infra.tunnel import NgrokTunnel, _agent_tunnels, _tail, open_tunnel

DOMAIN = "cops.ngrok-free.app"
PUBLIC = f"https://{DOMAIN}"
UNAUTHENTICATED = "ERR_NGROK_4018 authentication failed: this account is not verified"
TAKEN = "ERR_NGROK_334 the domain is already bound to another endpoint"


def published(port: int, *urls: str) -> list[dict]:
    # The shape ngrok's API answers in: it echoes our port back as `localhost`.
    return [{"public_url": url, "config": {"addr": f"http://localhost:{port}"}} for url in urls]


class FakeProcess:
    def __init__(self, deaf: bool = False) -> None:
        self.exit_code: int | None = None
        self.terminated = False
        self.killed = False
        self._deaf = deaf  # ignores terminate, as a wedged agent would

    def poll(self) -> int | None:
        return self.exit_code

    def terminate(self) -> None:
        self.terminated = True
        if not self._deaf:
            self.exit_code = -15

    def wait(self, timeout=None) -> int | None:
        if self._deaf:
            raise subprocess.TimeoutExpired("ngrok", timeout)
        return self.exit_code

    def kill(self) -> None:
        self.killed = True


class FakeNgrok:
    """ngrok as this module can see it: PATH, one child process, the 4040 API."""

    def __init__(self, monkeypatch, tunnels=(), *, already_up=False, dies_saying=None) -> None:
        self.tunnels = list(tunnels)
        self.dies_saying = dies_saying
        self.publish_after = 0  # API polls before the tunnel appears
        self.reported = self.tunnels if already_up else []
        self.commands: list[list[str]] = []
        self.processes: list[FakeProcess] = []
        self._polls = 0
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ngrok")
        monkeypatch.setattr("subprocess.Popen", self._start)
        monkeypatch.setattr("urllib.request.urlopen", self._api)
        monkeypatch.setattr("time.sleep", lambda seconds: None)

    def _start(self, command, **_) -> FakeProcess:
        self.commands.append(command)
        process = FakeProcess()
        if self.dies_saying is not None:
            self.log_of(command).write_text(self.dies_saying, encoding="utf-8")
            process.exit_code = 1
        self.processes.append(process)
        return process

    def _api(self, url, timeout=None) -> io.BytesIO:
        self._polls += 1
        if self.commands and self._polls > self.publish_after:
            self.reported = self.tunnels
        return io.BytesIO(json.dumps({"tunnels": self.reported}).encode())

    @staticmethod
    def log_of(command: list[str]) -> Path:
        return Path(next(arg for arg in command if arg.startswith("--log=")).split("=", 1)[1])


def test_the_public_address_comes_from_ngroks_own_agent_api(monkeypatch):
    # And it is the /mcp endpoint, not the bare origin, that is any use to them.
    FakeNgrok(monkeypatch, published(8801, PUBLIC))

    opened = open_tunnel(8801)

    assert (opened.public_url, opened.mcp_url) == (PUBLIC, f"{PUBLIC}/mcp")


def test_the_command_line_asks_for_the_reserved_domain_and_carries_no_secret(monkeypatch):
    """The token lives in ngrok's own config and nowhere near this repository."""
    ngrok = FakeNgrok(monkeypatch, published(8801, PUBLIC))

    open_tunnel(8801, DOMAIN)

    assert f"--domain={DOMAIN}" in ngrok.commands[0]
    assert not [arg for arg in ngrok.commands[0] if "token" in arg.lower()]


def test_ngrok_picks_the_address_when_no_domain_is_reserved(monkeypatch):
    """The ephemeral case: it plays, but on a different URL after every restart."""
    ngrok = FakeNgrok(monkeypatch, published(8801, "https://a1b2.ngrok-free.app"))

    assert open_tunnel(8801).public_url == "https://a1b2.ngrok-free.app"
    assert not [arg for arg in ngrok.commands[0] if arg.startswith("--domain")]


def test_it_keeps_polling_until_the_tunnel_is_really_published(monkeypatch):
    # The agent API answers long before it has anything to forward.
    FakeNgrok(monkeypatch, published(8801, PUBLIC)).publish_after = 3

    assert open_tunnel(8801).public_url == PUBLIC


def test_an_ngrok_that_is_not_installed_says_how_to_install_it(monkeypatch):
    FakeNgrok(monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(ConfigError, match="not on PATH"):
        open_tunnel(8801)


def test_an_unauthenticated_ngrok_says_exactly_which_command_to_run(monkeypatch):
    FakeNgrok(monkeypatch, dies_saying=UNAUTHENTICATED)

    with pytest.raises(ConfigError, match="ngrok config add-authtoken"):
        open_tunnel(8801, DOMAIN)


def test_a_domain_someone_else_is_holding_is_named(monkeypatch):
    FakeNgrok(monkeypatch, dies_saying=TAKEN)

    with pytest.raises(ConfigError, match=DOMAIN):
        open_tunnel(8801, DOMAIN)


def test_any_other_early_exit_quotes_ngrok_rather_than_guessing(monkeypatch):
    FakeNgrok(monkeypatch, dies_saying="something the course never mentioned")

    with pytest.raises(TransportError, match="something the course never mentioned"):
        open_tunnel(8801)


def test_a_tunnel_that_never_comes_up_leaves_no_agent_behind(monkeypatch):
    # A survivor would keep the reserved domain bound and fail the next run too.
    ngrok = FakeNgrok(monkeypatch)

    with pytest.raises(TransportError, match="published no tunnel"):
        open_tunnel(8801, DOMAIN, timeout=0.0)
    assert ngrok.processes[0].terminated


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


def test_a_tunnel_already_on_my_port_is_adopted_rather_than_duplicated(monkeypatch):
    """A second agent would only fight the first for the domain and the 4040 API.

    The https URL wins: ngrok may publish both schemes for one forwarded port.
    """
    published_both = published(8801, "http://insecure.example", PUBLIC)
    ngrok = FakeNgrok(monkeypatch, published_both, already_up=True)

    adopted = open_tunnel(8801, DOMAIN)
    adopted.close()  # closing must not kill a tunnel we did not start

    assert (adopted.public_url, ngrok.commands, ngrok.processes) == (PUBLIC, [], [])


def test_a_tunnel_forwarding_to_another_port_is_not_mine(monkeypatch):
    # The development case: the thief's tunnel is up, and is no use to me.
    ngrok = FakeNgrok(monkeypatch, published(8801, PUBLIC))
    ngrok.reported = published(8802, "https://thief.example")

    assert open_tunnel(8801).public_url == PUBLIC
    assert len(ngrok.commands) == 1


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
