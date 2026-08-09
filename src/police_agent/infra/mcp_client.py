"""Outbound MCP transport with reference-v3 session reuse and pacing.

The original client opened and closed a FastMCP session for every turn. That
works on localhost but is fragile through an HTTPS/ngrok endpoint: it creates a
new MCP handshake for every message, races free-plan request limits, and makes
an opponent's transient disconnect look like a dead game. The production SDK
now holds one client session and reconnects it through the existing retry loop.

The public surface remains synchronous and small so the game loop and its fake
transport stay unchanged. The persistent async FastMCP client lives on one
daemon event-loop thread and is only enabled after ``open()``; direct test
transports therefore keep the original simple call path.
"""

from __future__ import annotations

import asyncio
import contextlib
import queue
import threading
import time

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from police_agent.exceptions import TransportError
from police_agent.infra.mcp_server import PeerInboxes

TUNNEL_HEADERS = {"ngrok-skip-browser-warning": "1"}


def _http_transport(url: str) -> StreamableHttpTransport:
    """Build the HTTP transport used by both one-shot and persistent calls."""
    return StreamableHttpTransport(url, headers=TUNNEL_HEADERS)


class _PersistentMcpSession:
    """A synchronous facade over one async FastMCP client session."""

    def __init__(self, url: str, default_timeout: float, requests_per_minute: int) -> None:
        self._url = url
        self._default_timeout = default_timeout
        self._interval = 60.0 / max(1, int(requests_per_minute))
        self._pace_lock = threading.Lock()
        self._next_request = 0.0
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._client: Client | None = None
        self._thread = threading.Thread(
            target=self._thread_main,
            name="police-mcp-session",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise TransportError("Persistent MCP session event loop did not start")

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._stop = asyncio.Event()
        self._ready.set()
        try:
            loop.run_until_complete(self._serve())
        finally:
            loop.close()

    async def _serve(self) -> None:
        assert self._stop is not None
        await self._stop.wait()
        await self._close_client()

    async def _close_client(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            with contextlib.suppress(Exception):
                await client.__aexit__(None, None, None)

    async def _invoke(self, tool: str, arguments: dict, timeout: float) -> None:
        if self._client is None:
            client = Client(
                _http_transport(self._url),
                timeout=timeout,
                init_timeout=timeout,
            )
            try:
                await client.__aenter__()
            except Exception:
                with contextlib.suppress(Exception):
                    await client.__aexit__(None, None, None)
                raise
            self._client = client
        try:
            await self._client.call_tool(tool, arguments, timeout=timeout)
        except Exception:
            # The next retry gets a genuinely fresh MCP session. This is the
            # one reconnect boundary; the outer transport deadline controls how
            # long we continue trying after it.
            await self._close_client()
            raise

    def call(self, tool: str, arguments: dict, timeout: float | None = None) -> None:
        if self._loop is None or self._stop is None or self._stop.is_set():
            raise TransportError("Persistent MCP session is closed")
        budget = self._default_timeout if timeout is None else timeout
        with self._pace_lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request - now)
            self._next_request = max(now, self._next_request) + self._interval
        if delay:
            time.sleep(delay)
        future = asyncio.run_coroutine_threadsafe(self._invoke(tool, arguments, budget), self._loop)
        try:
            future.result(timeout=budget + 5.0)
        except Exception:
            future.cancel()
            raise

    def close(self) -> None:
        loop, stop = self._loop, self._stop
        if loop is None or stop is None or stop.is_set():
            return
        future = asyncio.run_coroutine_threadsafe(self._set_stop(), loop)
        with contextlib.suppress(Exception):
            future.result(timeout=5.0)
        self._thread.join(timeout=5.0)

    async def _set_stop(self) -> None:
        assert self._stop is not None
        self._stop.set()


class McpTransport:
    """One peer's view of the wire: push to the opponent, pull from my inbox."""

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
        requests_per_minute: int = 30,
    ) -> None:
        self._url = opponent_url
        self._inboxes = inboxes
        self._connect_timeout = connect_timeout
        self._retry_interval = retry_interval
        self._reply_timeout = reply_timeout
        self._audit_send_timeout = audit_send_timeout
        self._call_timeout = call_timeout
        self._control_send_timeout = control_send_timeout
        self._requests_per_minute = requests_per_minute
        self._persistent: _PersistentMcpSession | None = None
        self.dialect = "native"

    def set_dialect(self, dialect: str) -> McpTransport:
        """Select the wire dialect used by a runtime built on this transport."""
        self.dialect = str(dialect)
        return self

    def open(self) -> McpTransport:
        """Start the reusable session without requiring the opponent to be up yet."""
        if self._persistent is None:
            self._persistent = _PersistentMcpSession(
                self._url, self._call_timeout, self._requests_per_minute
            )
        return self

    def close(self) -> None:
        session, self._persistent = self._persistent, None
        if session is not None:
            session.close()

    def _call(self, tool: str, arguments: dict, timeout: float | None = None) -> None:
        """Invoke one tool, using the held session when the SDK opened it."""
        budget = self._call_timeout if timeout is None else timeout
        if self._persistent is not None:
            self._persistent.call(tool, arguments, budget)
            return

        async def invoke() -> None:
            async with Client(
                _http_transport(self._url),
                timeout=budget,
                init_timeout=budget,
            ) as client:
                await client.call_tool(tool, arguments, timeout=budget)

        asyncio.run(invoke())

    def _send_with_retry(self, tool: str, arguments: dict, timeout: float | None = None) -> None:
        """Retry until the opponent answers or the deadline passes."""
        deadline = time.monotonic() + (self._connect_timeout if timeout is None else timeout)
        while True:
            try:
                self._call(tool, arguments, timeout=self._call_timeout)
                return
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise TransportError(
                        f"Opponent MCP server unreachable at {self._url}: {exc}"
                    ) from exc
                time.sleep(self._retry_interval)

    def exchange_agreement(self, signed: dict) -> dict:
        """Send my signed agreement and block until the opponent's arrives."""
        self._send_with_retry("negotiate", {"message": signed})
        try:
            return self._inboxes.agreements.get(timeout=self._connect_timeout)
        except queue.Empty as exc:
            raise TransportError(f"No agreement from the opponent at {self._url}") from exc

    def send_turn(self, message: dict) -> None:
        """Hand my turn to the opponent."""
        self._send_with_retry("receive_turn", {"message": message})

    def poll_turn(self, timeout: float) -> dict | None:
        """Wait for the opponent's turn; ``None`` means the deadline expired."""
        try:
            return self._inboxes.turns.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_turns(self, timeout: float = 0.0) -> list[dict]:
        """Drain queued turns, waiting only for the first late terminal message."""
        drained: list[dict] = []
        deadline = time.monotonic() + max(0.0, timeout)
        first = True
        while True:
            try:
                wait = max(0.0, deadline - time.monotonic()) if first else 0.0
                drained.append(self._inboxes.turns.get(timeout=wait))
            except queue.Empty:
                return drained
            first = False

    def poll_control(self) -> dict | None:
        """Take one advisory session signal without blocking."""
        try:
            return self._inboxes.controls.get_nowait()
        except queue.Empty:
            return None

    def send_control(self, message: dict) -> None:
        """Best-effort control send; it must never stall the game."""
        with contextlib.suppress(Exception):
            self._call("receive_control", {"message": message}, timeout=self._control_send_timeout)

    def exchange_audit(self, payload: dict) -> dict | None:
        """Reveal my records and collect the opponent's, if it still answers."""
        with contextlib.suppress(TransportError):
            self._send_with_retry("submit_audit", {"payload": payload}, self._audit_send_timeout)
        try:
            return self._inboxes.audits.get(timeout=self._reply_timeout)
        except queue.Empty:
            return None

    def drain_inboxes(self) -> None:
        """Discard stale mail while preserving the next handshake agreement."""
        for inbox in (self._inboxes.turns, self._inboxes.controls, self._inboxes.audits):
            with contextlib.suppress(queue.Empty):
                while True:
                    inbox.get_nowait()
