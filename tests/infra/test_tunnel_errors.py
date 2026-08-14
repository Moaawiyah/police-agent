"""Every way opening an ngrok tunnel can fail, split out of test_tunnel.py to
keep both files under the project's line budget. See test_tunnel.py's
docstring for why ngrok is faked whole rather than checked by hand.
"""

import pytest

from police_agent.exceptions import ConfigError, TransportError
from police_agent.infra.tunnel import open_tunnel
from tests.infra.fake_ngrok import DOMAIN, TAKEN, UNAUTHENTICATED, FakeNgrok


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
