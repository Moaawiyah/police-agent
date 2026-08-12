"""Lazy, injectable SDK facade for configuring and playing a police match."""

from pathlib import Path

from police_agent.constants import Role
from police_agent.infra.mcp_client import McpTransport, peer_gate
from police_agent.infra.mcp_server import start_peer_server
from police_agent.infra.tunnel import open_tunnel
from police_agent.peer.controls import GameControls
from police_agent.peer.runtime import PoliceRuntime
from police_agent.sdk.league import validate_league, validate_tunnel_endpoint
from police_agent.sdk.options import MatchOptions
from police_agent.sdk.reporting import (
    email_report,
    load_summary,
    save_summary,
    write_artifacts,
)
from police_agent.sdk.series import play_series
from police_agent.shared.config import load_config

__all__ = [
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_REPLY_TIMEOUT",
    "DEFAULT_REPORT_DIR",
    "GameControls",
    "PoliceAgentSDK",
]

DEFAULT_REPORT_DIR = "logs"
DEFAULT_CONNECT_TIMEOUT = 60.0
DEFAULT_REPLY_TIMEOUT = 30.0


class PoliceAgentSDK:
    """The police agent's public API: configure it, connect it, play a sub-game."""

    def __init__(
        self, options=None, *, config=None, transport=None, listener=None, controls=None
    ) -> None:
        """Hold this match's options and config; nothing connects until `connect()`."""
        self.options = options or MatchOptions()
        self.config = config if config is not None else load_config(self.options.config_dir)
        self._transport = transport
        self._runtime: PoliceRuntime | None = None
        self._tunnel = None
        self.listener = listener
        self.controls = controls

    @property
    def host(self) -> str:
        """The bind host for this peer's own MCP server."""
        return self.options.host

    @property
    def port(self) -> int:
        """The bind port for this peer's own MCP server."""
        return int(self.options.port or self.config.require("network.my_port"))

    @property
    def opponent_url(self) -> str:
        """The URL this peer pushes turns to."""
        return str(self.options.opponent_url or self.config.require("network.opponent_url"))

    @property
    def tunnel_domain(self) -> str | None:
        """The reserved ngrok domain to publish on, if configured."""
        domain = self.config.get("network.tunnel_domain")
        return str(domain) if domain else None

    @property
    def public_url(self) -> str | None:
        """This peer's public tunnel URL, once one is open."""
        return self._tunnel.mcp_url if self._tunnel else None

    def connect(self):
        """Open this peer's own server and build the transport to the opponent, once."""
        validate_league(self, DEFAULT_CONNECT_TIMEOUT)
        if self._transport is None:
            inboxes = start_peer_server(
                Role.POLICE,
                self.host,
                self.port,
                # queue_depth, not requests_per_minute: the latter budgets the
                # OUTBOUND Gmail-reporting gate (ch. 9.3.1), an unrelated
                # pipeline with an unrelated cadence. See mcp_server.py's
                # DEFAULT_DOS_LIMIT_PER_MINUTE for the full reasoning.
                dos_limit_per_minute=float(self.config.get("gatekeeper.queue_depth") or 100.0)
                * 60.0,
            )
            self._open_tunnel()
            self._transport = McpTransport(
                self.opponent_url,
                inboxes,
                gate=peer_gate(self.config),
                **self.transport_timeouts(),
            )
        return self._transport

    def _open_tunnel(self) -> None:
        if self.options.tunnel and self._tunnel is None:
            self._tunnel = open_tunnel(self.port, self.tunnel_domain)
            if self.options.league:
                validate_tunnel_endpoint(self)

    def transport_timeouts(self) -> dict:
        """The agreed connect/reply timeouts, read from config."""
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
        """The active `PoliceRuntime`, building one (and connecting) on first use."""
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
        """Play one sub-game to a result."""
        return self.runtime.run()

    def play_series(self) -> list[dict]:
        """Play the whole agreed series."""
        return play_series(self)

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
        """Read a saved match summary from `path`."""
        return load_summary(path)

    def save_summary(self, summary: dict, path: str | Path) -> Path:
        """Write `summary` to `path` as JSON."""
        return save_summary(summary, path)

    def write_artifacts(self, summary: dict, base: str | Path = DEFAULT_REPORT_DIR) -> dict:
        """Write this match's mandatory report artifacts under `base`."""
        return write_artifacts(summary, base, self.config)

    def email_report(self, paths: dict) -> str | None:
        """Mail (or draft) the report at `paths`, per this peer's `[email]` config."""
        return email_report(paths, self.config)
