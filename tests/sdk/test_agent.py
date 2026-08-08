"""The SDK facade: settings resolution and opening the transport.

League-mode validation lives in test_agent_league.py; runtime lifecycle and
playing/persisting a match live in test_agent_lifecycle.py -- split three ways
so each file stays under the project's 150-line rule.
"""

import pytest

from police_agent.constants import Role
from police_agent.exceptions import ConfigError
from police_agent.infra.tunnel import NgrokTunnel
from police_agent.sdk import MatchOptions, PoliceAgentSDK
from tests.conftest import CONFIG_DIR, config_with
from tests.peer.fake_transport import FakeTransport
from tests.sdk.conftest import _forbidden, agent_with, record_wiring


def test_the_settings_come_from_the_config_when_nothing_overrides_them():
    agent = agent_with()

    assert (agent.host, agent.port) == ("127.0.0.1", 8801)
    assert agent.opponent_url == "http://127.0.0.1:8802/mcp"


def test_the_caller_may_override_the_port_and_the_opponent():
    """Two peers on one machine is the development case; without overrides both
    would read the same private config and try to bind the same port."""
    options = MatchOptions(host="0.0.0.0", port=9001, opponent_url="http://elsewhere/mcp")

    agent = agent_with(options=options)

    assert (agent.host, agent.port) == ("0.0.0.0", 9001)
    assert agent.opponent_url == "http://elsewhere/mcp"


def test_a_missing_port_is_reported_by_name():
    agent = PoliceAgentSDK(config=config_with(), transport=FakeTransport())

    with pytest.raises(ConfigError, match="network.my_port"):
        _ = agent.port


def test_a_missing_opponent_url_is_reported_by_name():
    agent = PoliceAgentSDK(config=config_with(), transport=FakeTransport())

    with pytest.raises(ConfigError, match="network.opponent_url"):
        _ = agent.opponent_url


def test_the_config_is_loaded_from_the_options_directory_when_none_is_given():
    agent = PoliceAgentSDK(MatchOptions(config_dir=CONFIG_DIR))

    assert agent.config.require("board.size") == 7


def test_an_injected_transport_is_never_replaced_by_a_socket(monkeypatch):
    """The seam that keeps the whole loop testable: if `connect` could reach past
    an injected double, every SDK test would need a live port."""
    monkeypatch.setattr("police_agent.sdk.agent.start_peer_server", _forbidden("started a server"))
    double = FakeTransport()

    agent = agent_with(transport=double)

    assert agent.connect() is double


def test_connect_opens_this_peers_mailbox_and_dials_the_opponent(monkeypatch):
    opened, dialled = record_wiring(monkeypatch)

    transport = agent_with(transport=None).connect()

    assert opened == [(Role.POLICE, "127.0.0.1", 8801)]
    assert dialled[0][0] == "http://127.0.0.1:8802/mcp"
    assert transport is dialled[0][2]


def test_the_wire_deadlines_come_from_the_agreed_terms():
    """Both peers read them from the byte-identical game.json, so the two sides
    wait the same length of time; a number frozen into the code would not."""
    agent = agent_with(network__watchdog_timeout_seconds=90, network__response_timeout_seconds=45)

    assert agent.transport_timeouts() == {"connect_timeout": 90.0, "reply_timeout": 45.0}


def test_the_deadlines_fall_back_when_the_terms_name_neither():
    """The shipped game.json names both, so these numbers should never decide a
    match -- but a partial file must not leave the transport with a None budget."""
    agent = agent_with(
        network__watchdog_timeout_seconds=None, network__response_timeout_seconds=None
    )

    assert agent.transport_timeouts() == {"connect_timeout": 60.0, "reply_timeout": 30.0}


def test_connecting_twice_opens_one_server(monkeypatch):
    """The second bind would fail on the port the first is holding."""
    opened, _ = record_wiring(monkeypatch)
    agent = agent_with(transport=None)

    assert agent.connect() is agent.connect()
    assert len(opened) == 1


def test_a_default_run_has_no_public_address_at_all(monkeypatch):
    record_wiring(monkeypatch)
    agent = agent_with(transport=None)

    agent.connect()

    assert agent.public_url is None


def test_the_tunnel_publishes_my_port_on_my_reserved_domain(monkeypatch):
    """The domain is private, so it comes from game.toml: no opponent verifies it."""
    record_wiring(monkeypatch)
    asked: list = []

    def open_tunnel(port, domain=None):
        asked.append((port, domain))
        return NgrokTunnel(f"https://{domain}")

    monkeypatch.setattr("police_agent.sdk.agent.open_tunnel", open_tunnel)
    options = MatchOptions(tunnel=True)
    agent = agent_with(transport=None, options=options, network__tunnel_domain="cops.ngrok.app")

    agent.connect()

    assert asked == [(8801, "cops.ngrok.app")]
    assert agent.public_url == "https://cops.ngrok.app/mcp"  # the /mcp mount, not the origin
