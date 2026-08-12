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
frozen into a method body.
"""

import asyncio
import contextlib
import queue
import time

from fastmcp import Client

from police_agent.exceptions import TransportError
from police_agent.infra.mcp_server import PeerInboxes


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
    ) -> None:
        self._url = opponent_url
        self._inboxes = inboxes
        self._connect_timeout = connect_timeout
        self._retry_interval = retry_interval
        self._reply_timeout = reply_timeout
        self._audit_send_timeout = audit_send_timeout
        self._call_timeout = call_timeout
        self._control_send_timeout = control_send_timeout

    @property
    def inbound_dos(self):
        """The detector watching THIS peer's own inbound mailbox for a flood."""
        return self._inboxes.inbound_dos

    def _call(self, tool: str, arguments: dict, timeout: float | None = None) -> None:
        """One MCP call: connect, invoke, disconnect.

        A fresh session per call keeps no state to go stale across the long,
        human-speed gaps between turns; the cost is one handshake per message,
        which is nothing next to a turn.
        """
        budget = self._call_timeout if timeout is None else timeout

        async def invoke() -> None:
            async with Client(self._url, timeout=budget, init_timeout=budget) as client:
                await client.call_tool(tool, arguments)

        asyncio.run(invoke())

    def _send_with_retry(self, tool: str, arguments: dict, timeout: float | None = None) -> None:
        """Retry until the opponent answers or the deadline passes.

        Two independently launched processes never start at the same instant, so
        "connection refused" during the opening seconds is the expected case, not
        an error. Only a deadline turns it into one.
        """
        deadline = time.monotonic() + (self._connect_timeout if timeout is None else timeout)
        while True:
            try:
                self._call(tool, arguments)
                return
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise TransportError(
                        f"Opponent MCP server unreachable at {self._url}: {exc}"
                    ) from exc
                time.sleep(self._retry_interval)

    def exchange_agreement(self, signed: dict) -> dict:
        """Send my signed agreement and block until the opponent's arrives.

        The handshake is where startup skew is largest, so it waits the full
        connect budget rather than the shorter per-turn reply budget.
        """
        self._send_with_retry("negotiate", {"message": signed})
        try:
            return self._inboxes.agreements.get(timeout=self._connect_timeout)
        except queue.Empty as exc:
            raise TransportError(f"No agreement from the opponent at {self._url}") from exc

    def send_turn(self, message: dict) -> None:
        """Hand my turn -- and with it the right to move -- to the opponent."""
        self._send_with_retry("receive_turn", {"message": message})

    def poll_turn(self, timeout: float) -> dict | None:
        """Wait for the opponent's turn. None means it ran out of time, not that it lost."""
        try:
            return self._inboxes.turns.get(timeout=timeout)
        except queue.Empty:
            return None

    def poll_control(self) -> dict | None:
        """Take one advisory session signal if any is waiting; never blocks the game."""
        try:
            return self._inboxes.controls.get_nowait()
        except queue.Empty:
            return None

    def send_control(self, message: dict) -> None:
        """Best-effort control send: a short timeout and swallowed errors, since
        this is advisory only and must never stall the game the way a missed
        turn or audit reveal would."""
        with contextlib.suppress(Exception):
            self._call("receive_control", {"message": message}, timeout=self._control_send_timeout)

    def exchange_audit(self, payload: dict) -> dict | None:
        """Reveal my sealed records and collect the opponent's, if it still answers.

        The send is best-effort on a short budget: a peer that already knows it
        won may exit the moment it has read its inbox, killing its server while
        our call is in flight even though the payload landed. Their reveal may
        well be sitting in our inbox regardless, so we always look.
        """
        with contextlib.suppress(TransportError):
            self._send_with_retry("submit_audit", {"payload": payload}, self._audit_send_timeout)
        try:
            return self._inboxes.audits.get(timeout=self._reply_timeout)
        except queue.Empty:
            return None

    def drain_inboxes(self) -> None:
        """Discard stale mail so a restarted sub-game cannot inherit the last one's.

        Agreements are left alone: both peers drain before re-negotiating, and no
        turn is sent until the fresh handshake has completed, so a queued
        agreement here is always the new one.
        """
        for inbox in (self._inboxes.turns, self._inboxes.controls, self._inboxes.audits):
            with contextlib.suppress(queue.Empty):
                while True:
                    inbox.get_nowait()
