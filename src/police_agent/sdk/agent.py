"""Lazy, injectable SDK facade for configuring and playing a police match."""

from pathlib import Path

from police_agent.constants import Role
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import start_peer_server
from police_agent.infra.tunnel import open_tunnel
from police_agent.peer.runtime import PoliceRuntime
from police_agent.sdk.league import (
    validate_league,
    validate_public_opponent,
    validate_tunnel_endpoint,
)
from police_agent.sdk.options import MatchOptions
from police_agent.sdk.reporting import (
    email_report,
    load_summary,
    save_summary,
    write_artifacts,
)
from police_agent.shared.config import load_config

DEFAULT_REPORT_DIR = "logs"
DEFAULT_CONNECT_TIMEOUT = 60.0
DEFAULT_REPLY_TIMEOUT = 30.0


class PoliceAgentSDK:
    """The police agent's public API: configure it, connect it, play a sub-game."""

    def __init__(
        self, options=None, *, config=None, transport=None, listener=None, controls=None
    ) -> None:
        self.options = options or MatchOptions()
        self.config = config if config is not None else load_config(self.options.config_dir)
        self._transport = transport
        self._runtime: PoliceRuntime | None = None
        self._tunnel = None
        self.listener = listener
        self.controls = controls

    @property
    def host(self) -> str:
        return self.options.host

    @property
    def port(self) -> int:
        return int(self.options.port or self.config.require("network.my_port"))

    @property
    def opponent_url(self) -> str:
        return str(self.options.opponent_url or self.config.require("network.opponent_url"))

    @property
    def tunnel_domain(self) -> str | None:
        domain = self.config.get("network.tunnel_domain")
        return str(domain) if domain else None

    @property
    def public_url(self) -> str | None:
        return self._tunnel.mcp_url if self._tunnel else None

    def connect(self):
        self._validate_league()
        if self._transport is None:
            inboxes = start_peer_server(Role.POLICE, self.host, self.port)
            self._open_tunnel()
            self._transport = McpTransport(self.opponent_url, inboxes, **self.transport_timeouts())
        return self._transport

    def _open_tunnel(self) -> None:
        if self.options.tunnel and self._tunnel is None:
            self._tunnel = open_tunnel(self.port, self.tunnel_domain)
            if self.options.league:
                self._validate_tunnel_endpoint()

    def _validate_league(self) -> None:
        validate_league(self, DEFAULT_CONNECT_TIMEOUT)

    @staticmethod
    def _validate_public_opponent(url: str) -> None:
        validate_public_opponent(url)

    def _validate_tunnel_endpoint(self) -> None:
        validate_tunnel_endpoint(self)

    def transport_timeouts(self) -> dict:
        return {
            "connect_timeout": float(
                self.config.get("network.watchdog_timeout_seconds") or DEFAULT_CONNECT_TIMEOUT
            ),
            "reply_timeout": float(
                self.config.get("network.response_timeout_seconds") or DEFAULT_REPLY_TIMEOUT
            ),
        }

    @property
    def runtime(self) -> PoliceRuntime:
        if self._runtime is None:
            self._runtime = PoliceRuntime(
                self.config,
                self.connect(),
                listener=self.listener,
                controls=self.controls,
                league=self.options.league,
            )
        return self._runtime

    def play(self) -> dict:
        return self.runtime.run()

    def restart(self) -> None:
        """Drop the finished runtime so the next `play()` builds a fresh one.

        The transport (and the server bound to this port) is left untouched
        and reused -- rebinding it would race the port the old one still
        holds. Only the game state is new: a fresh `PoliceRuntime` negotiates
        its own handshake in `run()`, so this never re-arms a runtime that has
        already agreed its terms (`gui/live_controls.py`'s Start button is
        deliberately not re-armable for that exact reason).
        """
        self._runtime = None

    def load_summary(self, path: str | Path) -> dict:
        return load_summary(path)

    def save_summary(self, summary: dict, path: str | Path) -> Path:
        return save_summary(summary, path)

    def write_artifacts(self, summary: dict, base: str | Path = DEFAULT_REPORT_DIR) -> dict:
        return write_artifacts(summary, base, self.config)

    def email_report(self, paths: dict) -> str | None:
        return email_report(paths, self.config)
