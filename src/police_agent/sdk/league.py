"""League-profile validation for the SDK facade."""

import ipaddress
from urllib.parse import urlparse

from police_agent.exceptions import ConfigError


def validate_league(agent, default_connect_timeout: float) -> None:
    if not agent.options.league:
        return
    if not agent.options.tunnel:
        raise ConfigError("league mode requires --tunnel")
    if not agent.tunnel_domain:
        raise ConfigError("league mode requires network.tunnel_domain")
    validate_public_opponent(agent.opponent_url)
    private_timeout = agent.config.get("network.turn_timeout_seconds")
    watchdog = agent.config.get("network.watchdog_timeout_seconds") or default_connect_timeout
    if private_timeout is not None and float(private_timeout) != float(watchdog):
        raise ConfigError("league mode requires turn_timeout_seconds to equal watchdog_timeout_seconds")


def validate_public_opponent(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.scheme != "https" or not host:
        raise ConfigError("league mode requires an HTTPS opponent URL")
    lowered = host.lower()
    if lowered == "localhost" or lowered.endswith(".localhost"):
        raise ConfigError("league mode rejects localhost opponent URLs")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified:
        raise ConfigError("league mode rejects private opponent IP addresses")


def validate_tunnel_endpoint(agent) -> None:
    parsed = urlparse(agent._tunnel.public_url)
    if parsed.scheme != "https" or parsed.hostname != agent.tunnel_domain:
        raise ConfigError("league tunnel did not acquire the configured HTTPS reserved domain")
