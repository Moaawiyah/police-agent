"""`PoliceAgentSDK`'s connection-building mixin, split out of `agent.py` to
keep that file under the project's line budget.

Holds everything involved in standing up this peer's own server, tunnel and
transport, and the `PoliceRuntime` built on top of them. `agent.py` keeps the
lifecycle/reporting surface (`play`, `write_artifacts`, ...) and mixes this
class in, so callers never see the split -- `PoliceAgentSDK.connect()` is
just `_ConnectionMixin.connect`.
"""

from police_agent.constants import Role
from police_agent.infra.mcp_client import McpTransport, peer_gate
from police_agent.infra.mcp_server import start_peer_server
from police_agent.infra.tunnel import open_tunnel
from police_agent.peer.runtime import PoliceRuntime
from police_agent.sdk.league import validate_league, validate_tunnel_endpoint

DEFAULT_CONNECT_TIMEOUT = 60.0
DEFAULT_REPLY_TIMEOUT = 30.0


class _ConnectionMixin:
    """The transport/tunnel/runtime-building half of `PoliceAgentSDK`."""

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
