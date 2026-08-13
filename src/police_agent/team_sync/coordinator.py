"""Police's own team_sync coordinator: a tiny FastMCP server, bound to
`127.0.0.1` only, that the sibling Thief process calls into on this machine.

Mirrors the exact shape `infra/mcp_server.py` already proved for the
opponent-facing channel: a thin tool body drops the payload in a queue and
returns, a daemon thread serves it, `_ensure_port_free` fails fast rather
than leaving the game loop waiting on a port nothing is listening on. This
is a *second*, unrelated server -- never routed through `infra/tunnel.py`'s
ngrok path, which stays reserved for the real opponent.

Every inbound tool verifies the message's HMAC (`security.py`) before it is
ever queued; a bad signature is rejected and never reaches the scheduler.
`status_request` is answered inline rather than queued, since it is a
synchronous "where do things stand" query, not a mutation of series state.
"""

import queue
import socket
import threading

from fastmcp import FastMCP

from police_agent.exceptions import ConfigError
from police_agent.team_sync import security


def _ensure_port_free(host: str, port: int) -> None:
    """Refuse to start when this peer's own team_sync port is already taken."""
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


def build_coordinator(inboxes: CoordinatorInboxes, secret: str | None, status_provider) -> FastMCP:
    """Build (but do not run) the coordinator app. Unstarted, so a test can
    drive it over FastMCP's in-memory client without binding a socket."""
    mcp = FastMCP(name="police-team-sync")

    @mcp.tool
    def subgame_result(message: dict) -> dict:
        """Receive the sibling Thief's settled result for one even sub-game."""
        if not security.verify_message(message, secret):
            return {"ok": False, "error": "invalid hmac"}
        inboxes.subgame_results.put(message)
        return {"ok": True}

    @mcp.tool
    def ack(message: dict) -> dict:
        """Receive the sibling's best-effort ack of a `series_start`/`handoff`."""
        if not security.verify_message(message, secret):
            return {"ok": False, "error": "invalid hmac"}
        inboxes.acks.put(message)
        return {"ok": True}

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
