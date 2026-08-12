"""Two real MCP servers on two ports, talking to each other over HTTP.

This is the only test that proves the arrangement the specification actually
requires (ch. 2.4.2): two peers that share no memory, each hosting its own
server and knowing nothing about the other but a URL. Everything is localhost,
but nothing in the path is faked -- real sockets, real MCP sessions.

The servers run in daemon threads, so they cannot outlive the pytest process,
and every wait here is bounded.
"""

import socket

import pytest

from police_agent.constants import Role
from police_agent.exceptions import TransportError
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import start_peer_server
from police_agent.peer.protocol import AuditPayload, TurnMessage

HOST = "127.0.0.1"


def free_port() -> int:
    """Let the OS pick a port that is free right now, instead of guessing one."""
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def peers():
    """Two independent peers, each pointed only at the other's URL."""
    police_port, opponent_port = free_port(), free_port()
    police_inboxes = start_peer_server(Role.POLICE, HOST, police_port)
    opponent_inboxes = start_peer_server(Role.THIEF, HOST, opponent_port)
    # Generous connect budget: uvicorn needs a moment to bind, and a peer that
    # starts seconds after its opponent is the normal case, not a failure.
    settings = {"connect_timeout": 30.0, "retry_interval": 0.2, "reply_timeout": 10.0}
    police = McpTransport(f"http://{HOST}:{opponent_port}/mcp", police_inboxes, **settings)
    opponent = McpTransport(f"http://{HOST}:{police_port}/mcp", opponent_inboxes, **settings)
    return police, opponent


def a_turn(step: int, sender: str) -> TurnMessage:
    return TurnMessage(
        step=step,
        sender=sender,
        hint="last seen near the bridge",
        smell_grid={"2,3": 0.9},
        commit=f"commit-{step}",
        timestamp="2026-08-02T10:00:00",
    )


@pytest.mark.slow
def test_a_turn_sent_by_one_peer_arrives_at_the_other(peers):
    police, opponent = peers
    sent = a_turn(step=1, sender="police")

    police.send_turn(sent.to_dict())

    received = opponent.poll_turn(timeout=10.0)
    assert received is not None, "the turn never reached the opponent's inbox"
    assert TurnMessage.from_dict(received) == sent
    assert police.poll_turn(timeout=0.1) is None  # my own turn did not echo back to me


@pytest.mark.slow
def test_the_turn_hands_the_move_back_and_forth(peers):
    police, opponent = peers

    police.send_turn(a_turn(step=2, sender="police").to_dict())
    theirs = opponent.poll_turn(timeout=10.0)
    assert theirs is not None
    opponent.send_turn(a_turn(step=3, sender="thief").to_dict())
    mine = police.poll_turn(timeout=10.0)

    assert (theirs["step"], mine["step"]) == (2, 3)
    assert mine["sender"] == "thief"


@pytest.mark.slow
def test_the_handshake_completes_when_both_peers_send(peers):
    police, opponent = peers
    # The opponent pushes its agreement to me first, as it would if it had
    # started earlier; exchange_agreement then sends mine and reads theirs.
    opponent_agreement = {"group_id": "thief-team", "sha256": "abc"}
    opponent._send_with_retry("negotiate", {"message": opponent_agreement})

    theirs = police.exchange_agreement({"group_id": "police-team", "sha256": "abc"})

    assert theirs == opponent_agreement
    assert opponent._inboxes.agreements.get(timeout=10.0)["group_id"] == "police-team"


@pytest.mark.slow
def test_a_flooding_peer_is_rejected_over_the_real_link():
    """Its own, low-limit pair of servers -- flooding the shared `peers`
    fixture would trip it for every other test in this module."""
    opponent_port = free_port()
    opponent_inboxes = start_peer_server(Role.THIEF, HOST, opponent_port, dos_limit_per_minute=3)
    settings = {"connect_timeout": 5.0, "retry_interval": 0.05, "reply_timeout": 2.0}
    police = McpTransport(f"http://{HOST}:{opponent_port}/mcp", opponent_inboxes, **settings)

    for step in range(3):
        police.send_turn(a_turn(step=step, sender="police").to_dict())

    with pytest.raises(TransportError):
        police.send_turn(a_turn(step=3, sender="police").to_dict())


@pytest.mark.slow
def test_audits_cross_over_the_real_link(peers):
    police, opponent = peers
    theirs = AuditPayload(sender="thief", records=[], result_claim="survival")
    opponent._send_with_retry("submit_audit", {"payload": theirs.to_dict()})

    mine = AuditPayload(sender="police", records=[], result_claim="capture")
    returned = police.exchange_audit(mine.to_dict())

    assert AuditPayload.from_dict(returned) == theirs
    assert opponent._inboxes.audits.get(timeout=10.0)["sender"] == "police"
