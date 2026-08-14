"""Police's own team_sync coordinator: a tiny FastMCP server, bound to
`127.0.0.1` only, that the sibling Thief process calls into on this machine.

Mirrors the exact shape `infra/mcp_server.py` already proved for the
opponent-facing channel: a thin tool body drops the payload in a queue and
returns, a daemon thread serves it, `_ensure_port_free` fails fast rather
than leaving the game loop waiting on a port nothing is listening on. A
*second*, unrelated server -- never routed through `infra/tunnel.py`'s ngrok
path, reserved for the real opponent. Every inbound tool verifies the
message's HMAC (`security.py`) before it is ever queued; `status_request` is
answered inline rather than queued, since it is a query, not a mutation.
"""

import queue
import socket
import threading

from fastmcp import FastMCP

from police_agent.exceptions import ConfigError
from police_agent.team_sync import security


def _ensure_port_free(host: str, port: int) -> None:
    """Refuse to start when this peer's own team_sync port is already taken."""
    if host != "127.0.0.1":
        raise ConfigError("team_sync must bind to localhost 127.0.0.1")
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise ConfigError(
            f"team_sync port {port} on {host} is already in use - a previous run is "
            f"probably still alive. Find and stop it:\n"
            f"  lsof -nP -iTCP:{port} -sTCP:LISTEN\n"
            f"  kill <PID>\n"
            f"or change team_sync.port in config/police/game.toml."
        ) from exc
    finally:
        probe.close()


class CoordinatorInboxes:
    """The mailboxes the sibling Thief process fills; the scheduler drains them."""

    def __init__(self) -> None:
        """Two empty mailboxes: settled results, and best-effort acks of ours."""
        self.subgame_results: queue.Queue = queue.Queue()
        self.acks: queue.Queue = queue.Queue()
        self.series_start: queue.Queue = queue.Queue()
        self.handoff: queue.Queue = queue.Queue()
        self.series_complete: queue.Queue = queue.Queue()
        self._seen_message_ids: set[str] = set()
        self._seen_lock = threading.Lock()

    def first_delivery(self, message: dict) -> bool:
        """Deduplicate transport retries before they reach the scheduler."""
        message_id = str(message.get("message_id", ""))
        if not message_id:
            return True
        with self._seen_lock:
            if message_id in self._seen_message_ids:
                return False
            self._seen_message_ids.add(message_id)
            return True

    def clear(self) -> None:
        """Discard queued messages from a failed attempt before a fresh one."""
        for inbox in (self.subgame_results, self.acks, self.series_start, self.handoff,
                      self.series_complete):
            while not inbox.empty():
                inbox.get_nowait()
        with self._seen_lock:
            self._seen_message_ids.clear()


def _accept(inboxes: CoordinatorInboxes, secret: str | None, message: dict, inbox: queue.Queue) -> dict:
    """Verify HMAC, dedupe by message_id, and enqueue on first delivery -- shared
    by every tool below except `status_request`, which only reads state."""
    if not security.verify_message(message, secret):
        return {"ok": False, "error": "invalid hmac"}
    if not inboxes.first_delivery(message):
        return {"ok": True, "duplicate": True, "ack_for_message_id": message.get("message_id")}
    inbox.put(message)
    return {"ok": True, "ack_for_message_id": message.get("message_id")}


def build_coordinator(inboxes: CoordinatorInboxes, secret: str | None, status_provider) -> FastMCP:
    """Build (but do not run) the coordinator app. Unstarted, so a test can
    drive it over FastMCP's in-memory client without binding a socket."""
    mcp = FastMCP(name="police-team-sync")

    @mcp.tool
    def subgame_result(message: dict) -> dict:
        """Receive the sibling Thief's settled result for one even sub-game."""
        return _accept(inboxes, secret, message, inboxes.subgame_results)

    @mcp.tool
    def ack(message: dict) -> dict:
        """Receive the sibling's best-effort ack of a `series_start`/`handoff`."""
        return _accept(inboxes, secret, message, inboxes.acks)

    @mcp.tool
    def series_start(message: dict) -> dict:
        """Receive a Thief-started series announcement."""
        return _accept(inboxes, secret, message, inboxes.series_start)

    @mcp.tool
    def handoff(message: dict) -> dict:
        """Receive a settled-subgame handoff from the sibling Thief.

        Police normally already knows its next local turn, but accepting the
        same signed handoff on both coordinators keeps the wire symmetric and
        gives the receiver a validated, deduplicated synchronization record.
        """
        return _accept(inboxes, secret, message, inboxes.handoff)

    @mcp.tool
    def series_complete(message: dict) -> dict:
        """Receive the final-report notification."""
        return _accept(inboxes, secret, message, inboxes.series_complete)

    @mcp.tool
    def status_request(message: dict) -> dict:
        """Answer a resync request with this peer's current status, signed."""
        if not security.verify_message(message, secret):
            return {"ok": False, "error": "invalid hmac"}
        return security.sign_message(status_provider(), secret)

    return mcp


def start_coordinator(
    host: str, port: int, secret: str | None, status_provider
) -> tuple[CoordinatorInboxes, threading.Thread]:
    """Serve this peer's team_sync mailbox on `host:port` in a daemon thread."""
    _ensure_port_free(host, port)
    inboxes = CoordinatorInboxes()
    server = build_coordinator(inboxes, secret, status_provider)
    thread = threading.Thread(
        target=lambda: server.run(
            transport="http", host=host, port=port, show_banner=False, log_level="warning"
        ),
        daemon=True,
        name="team-sync-coordinator",
    )
    thread.start()
    return inboxes, thread
