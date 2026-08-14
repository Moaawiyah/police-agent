"""League-mode validation: the public-tunnel profile --league enforces.

Split from test_agent.py to keep both files under the project's 150-line rule.
"""

import pytest

from police_agent.exceptions import ConfigError
from police_agent.infra.tunnel import NgrokTunnel
from police_agent.sdk import MatchOptions
from tests.sdk.conftest import agent_with, record_wiring


@pytest.mark.parametrize(
    ("opponent", "error"),
    [
        ("http://thief.example/mcp", "HTTPS"),
        ("https://localhost/mcp", "localhost"),
        ("https://127.0.0.1/mcp", "private opponent"),
        ("https://10.0.0.2/mcp", "private opponent"),
    ],
)
def test_league_mode_rejects_non_public_opponents(opponent, error):
    agent = agent_with(
        options=MatchOptions(league=True, tunnel=True, opponent_url=opponent),
        network__tunnel_domain="cops.ngrok.app",
    )

    with pytest.raises(ConfigError, match=error):
        agent.connect()


def test_league_mode_requires_a_tunnel_and_reserved_domain():
    missing_tunnel = agent_with(
        options=MatchOptions(league=True, opponent_url="https://thief.example/mcp"),
        network__tunnel_domain="cops.ngrok.app",
    )
    missing_domain = agent_with(
        options=MatchOptions(league=True, tunnel=True, opponent_url="https://thief.example/mcp")
    )

    with pytest.raises(ConfigError, match="--tunnel"):
        missing_tunnel.connect()
    with pytest.raises(ConfigError, match="tunnel_domain"):
        missing_domain.connect()


def test_league_mode_rejects_a_private_turn_timeout():
    agent = agent_with(
        options=MatchOptions(league=True, tunnel=True, opponent_url="https://thief.example/mcp"),
        network__tunnel_domain="cops.ngrok.app",
        network__turn_timeout_seconds=180,
    )

    with pytest.raises(ConfigError, match="turn_timeout_seconds"):
        agent.connect()


def test_league_mode_uses_the_reserved_https_tunnel_and_watchdog(monkeypatch):
    opened, _ = record_wiring(monkeypatch)
    monkeypatch.setattr(
        "police_agent.sdk.agent_connection.open_tunnel",
        lambda port, domain: NgrokTunnel(f"https://{domain}"),
    )
    agent = agent_with(
        transport=None,
        options=MatchOptions(league=True, tunnel=True, opponent_url="https://thief.example/mcp"),
        network__tunnel_domain="cops.ngrok.app",
        network__turn_timeout_seconds=90,
        network__watchdog_timeout_seconds=90,
    )

    agent.connect()

    assert opened
    assert agent.public_url == "https://cops.ngrok.app/mcp"
    assert agent.runtime._turn_timeout() == 90.0


def test_league_mode_rejects_an_unreserved_tunnel_endpoint(monkeypatch):
    record_wiring(monkeypatch)
    monkeypatch.setattr(
        "police_agent.sdk.agent_connection.open_tunnel",
        lambda port, domain: NgrokTunnel("https://other.ngrok.app"),
    )
    agent = agent_with(
        transport=None,
        options=MatchOptions(league=True, tunnel=True, opponent_url="https://thief.example/mcp"),
        network__tunnel_domain="cops.ngrok.app",
    )

    with pytest.raises(ConfigError, match="configured HTTPS"):
        agent.connect()
