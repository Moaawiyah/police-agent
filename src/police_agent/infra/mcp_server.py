"""This peer's OWN FastMCP server: its public mailbox. There is no central server.

The specification (ch. 2.4.2, ch. 9.4) puts the two agents in two separate
processes with no shared memory, so the only way the opponent can reach us is by
calling a tool on the server we host ourselves. Everything here is the *inbound*
half of the link -- what the opponent pushes INTO this agent. The outbound half
lives in `mcp_client.py`.

The tools do no game reasoning at all: they drop the raw payload into a
thread-safe queue and return. Uvicorn serves each request on its own worker, so
the queue -- not the tool body -- is the hand-over point to the single-threaded
game loop that drains it. Keeping the tools this thin also means a slow or
crashing strategy can never stall the opponent's HTTP call.

Tool names are the wire contract with another team's implementation, so they
match the names used across the course's reference implementation.
"""

import queue
import socket
import threading

from fastmcp import FastMCP

from police_agent.constants import Role
from police_agent.exceptions import ConfigError


def _ensure_port_free(host: str, port: int) -> None:
    """Refuse to start when my own port is taken, instead of failing later.

    Uvicorn's own bind error surfaces deep inside a background thread where the
    game loop cannot see it: the peer would sit waiting for turns that can never
    arrive. Probing first turns that into an immediate, actionable error. This is
    a local configuration/environment problem, not a broken link to the
    opponent, hence ConfigError rather than TransportError.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise ConfigError(
            f"Port {port} on {host} is already in use - a previous peer is probably still "
            f"running. Find and stop it:\n"
            f"  lsof -nP -iTCP:{port} -sTCP:LISTEN\n"
            f"  kill <PID>\n"
            f"or change network.my_port in config/police/game.toml."
        ) from exc
    finally:
        probe.close()


class PeerInboxes:
    """Thread-safe mailboxes: filled by MCP tool calls, drained by the game loop.

    One queue per conversation so a late audit reveal can never be mistaken for
    the turn the loop is currently waiting on.
    """

    def __init__(self) -> None:
        self.agreements: queue.Queue = queue.Queue()
        self.turns: queue.Queue = queue.Queue()
        self.audits: queue.Queue = queue.Queue()
        self.controls: queue.Queue = queue.Queue()


def build_peer_server(role: Role, inboxes: PeerInboxes) -> FastMCP:
    """Build (but do not run) the MCP app exposing this peer's receive tools.

    Returned unstarted so tests can drive it over FastMCP's in-memory client
    without binding a socket.
    """
    mcp = FastMCP(name=f"police-thief-{role.value}")

    @mcp.tool
    def negotiate(message: dict) -> dict:
        """Receive the opponent's signed pre-game agreement."""
        inboxes.agreements.put(message)
        return {"ok": True}

    @mcp.tool
    def receive_turn(message: dict) -> dict:
        """Receive the opponent's turn message, which also passes the turn to me."""
        inboxes.turns.put(message)
        return {"ok": True}

    @mcp.tool
    def submit_audit(payload: dict) -> dict:
        """Receive the opponent's end-of-game reveal: sealed records plus nonces."""
        inboxes.audits.put(payload)
        return {"ok": True}

    @mcp.tool
    def receive_control(message: dict) -> dict:
        """Accept an advisory session signal (enable / status / restart / quit)."""
        inboxes.controls.put(message)
        return {"ok": True}

    return mcp


def start_peer_server(role: Role, host: str, port: int) -> PeerInboxes:
    """Serve this peer's mailbox on its own port and hand back the inboxes.

    The server runs in a daemon thread so the process still exits when the game
    ends: a peer that outlives its own match would keep the port bound and block
    the next run. Nothing is returned but the inboxes, because the game loop
    never needs to talk to the server -- only to read what arrived.
    """
    _ensure_port_free(host, port)
    inboxes = PeerInboxes()
    server = build_peer_server(role, inboxes)
    thread = threading.Thread(
        target=lambda: server.run(
            transport="http",
            host=host,
            port=port,
            show_banner=False,
            log_level="warning",  # per-request logs would bury the game output
        ),
        daemon=True,
        name=f"mcp-{role.value}",
    )
    thread.start()
    return inboxes
