"""McpTransport: the outbound half of the link -- what I push to the opponent.

There is no central server. This peer knows exactly one thing about the other
side: a URL (config `network.opponent_url`). Everything it sends goes to that
URL's MCP tools; everything it receives arrives asynchronously in the inboxes of
its own server (`mcp_server.py`) and is read back here. Which is why the polling
methods never touch the network at all.

The method surface below is intentionally small and carries plain dicts, so
the game loop can be driven in tests by a FakeTransport implementing the same
methods without a socket in sight.

Every timeout is a constructor argument, defaulted from config/police/game.json
(`response_timeout_sec` = 30, `watchdog_timeout_sec` = 60), so no policy is
frozen into a method body. The public methods themselves live in
`mcp_client_ops.py`, split out to keep this file under the project's line
budget -- see that module's docstring for why monkeypatching `_call` still
reaches them.

Every outbound call is admitted through a `Gatekeeper` (`shared/gatekeeper.py`)
before it touches the socket -- the same rule ch. 9.3.1 already applies to the
Gmail and Ollama channels (`infra/gmail.py`, `infra/ollama.py`). This gate's
`max_retries` is forced to 0: `_send_with_retry` below is this channel's own
retry policy, tuned for "the opponent has not started yet" rather than a slow
external API, and letting the gate retry too would silently double it.
"""

import asyncio
import time
from dataclasses import replace

from fastmcp import Client

from police_agent.exceptions import TransportError
from police_agent.infra import mcp_client_ops as ops
from police_agent.infra.mcp_server import PeerInboxes
from police_agent.shared.gatekeeper import Gatekeeper, GateLimits


def peer_gate(config=None) -> Gatekeeper:
    """The outbound MCP channel's gate: the agreed `gatekeeper.*` limits, minus retrying."""
    get = config.get if config is not None else (lambda _key, default=None: default)
    return Gatekeeper(replace(GateLimits.from_getter(get), max_retries=0))


class McpTransport:
    """One peer's view of the wire: push to the opponent's URL, pull from my inboxes."""

    def __init__(
        self,
        opponent_url: str,
        inboxes: PeerInboxes,
        connect_timeout: float = 60.0,
        retry_interval: float = 1.0,
        reply_timeout: float = 30.0,
        audit_send_timeout: float = 10.0,
        call_timeout: float = 10.0,
        control_send_timeout: float = 3.0,
        gate: Gatekeeper | None = None,
    ) -> None:
        """Store this peer's wire timeouts and build (or accept) its outbound gate."""
        self._url = opponent_url
        self._inboxes = inboxes
        self._connect_timeout = connect_timeout
        self._retry_interval = retry_interval
        self._reply_timeout = reply_timeout
        self._audit_send_timeout = audit_send_timeout
        self._call_timeout = call_timeout
        self._control_send_timeout = control_send_timeout
        self._gate = gate or peer_gate()

    @property
    def inbound_dos(self):
        """The detector watching THIS peer's own inbound mailbox for a flood."""
        return self._inboxes.inbound_dos

    def publish_greeting(self, signed: dict | None) -> None:
        """Make my signed greeting available to my own negotiate tool's reply."""
        self._inboxes.greeting = signed

    def _call(self, tool: str, arguments: dict, timeout: float | None = None) -> dict | None:
        """One MCP call: connect, invoke, disconnect, and hand back the reply.

        A fresh session per call keeps no state to go stale across the long,
        human-speed gaps between turns; the cost is one handshake per message,
        which is nothing next to a turn.

        The reply body is returned rather than dropped: a request/response peer
        answers `negotiate` with its own greeting there, and that is the only
        copy we get from a peer that never dials us back.
        """
        budget = self._call_timeout if timeout is None else timeout

        async def invoke() -> dict | None:
            """One connect-call-disconnect cycle over FastMCP."""
            async with Client(self._url, timeout=budget, init_timeout=budget) as client:
                reply = await client.call_tool(tool, arguments)
                return getattr(reply, "data", None) or getattr(reply, "structured_content", None)

        return self._gate.submit(lambda: asyncio.run(invoke()), budget=budget)

    def _send_with_retry(
        self, tool: str, arguments: dict, timeout: float | None = None
    ) -> dict | None:
        """Retry until the opponent answers or the deadline passes, returning its reply.

        Two independently launched processes never start at the same instant, so
        "connection refused" during the opening seconds is the expected case, not
        an error. Only a deadline turns it into one.
        """
        deadline = time.monotonic() + (self._connect_timeout if timeout is None else timeout)
        while True:
            try:
                return self._call(tool, arguments, timeout)
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise TransportError(
                        f"Opponent MCP server unreachable at {self._url}: {exc}"
                    ) from exc
                time.sleep(self._retry_interval)

    def exchange_agreement(self, signed: dict) -> dict:
        """Send my signed agreement and return the opponent's."""
        return ops.exchange_agreement(self, signed)

    def send_turn(self, message: dict) -> None:
        """Hand my turn to the opponent."""
        ops.send_turn(self, message)

    def poll_turn(self, timeout: float) -> dict | None:
        """Wait up to `timeout` for the opponent's turn."""
        return ops.poll_turn(self, timeout)

    def poll_control(self) -> dict | None:
        """Take one queued control signal, if any, without blocking."""
        return ops.poll_control(self)

    def send_control(self, message: dict) -> None:
        """Best-effort send of an advisory control signal."""
        ops.send_control(self, message)

    def exchange_audit(self, payload: dict) -> dict | None:
        """Reveal my sealed records and collect the opponent's, if it answers."""
        return ops.exchange_audit(self, payload)

    def drain_inboxes(self) -> None:
        """Discard any stale turns, controls and audits left from a prior sub-game."""
        ops.drain_inboxes(self)
