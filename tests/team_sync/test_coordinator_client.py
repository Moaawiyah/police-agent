"""Two real team_sync coordinators on two localhost ports, talking to each
other over HTTP -- mirrors `tests/infra/test_mcp_two_peers.py`. No LLM, no
real game: just the coordination envelopes and a stub status/summary.

This repo (Police-only, per CLAUDE.md) implements only Police's side of the
coordinator, which is deliberately a *smaller* inbound tool surface than the
Thief sibling's: Police mostly SENDS `series_start`/`handoff` and only
RECEIVES `subgame_result`/`ack`/`status_request` (see `coordinator.py`'s
docstring). So both ends of this test run that same Police-shaped
coordinator, and only the tools it actually exposes are exercised -- calling
`series_start` against it would correctly fail with "Unknown tool", which is
covered by `client.py`'s own retry/timeout tests rather than repeated here.
"""

import socket

import pytest

from police_agent.exceptions import TransportError
from police_agent.team_sync.client import TeamSyncClient
from police_agent.team_sync.coordinator import start_coordinator

HOST = "127.0.0.1"
SECRET = "shared-test-secret"


def free_port() -> int:
    """Let the OS pick a port that is free right now, instead of guessing one."""
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


@pytest.fixture
def linked_pair():
    """Two coordinators, each pointed only at the other's URL, sharing a secret."""
    police_port, thief_port = free_port(), free_port()
    police_inboxes, _ = start_coordinator(
        HOST, police_port, SECRET, lambda: {"state": "ready", "current_subgame": 1}
    )
    thief_inboxes, _ = start_coordinator(
        HOST, thief_port, SECRET, lambda: {"state": "waiting", "current_subgame": 1}
    )
    settings = {"connect_timeout": 15.0, "retry_interval": 0.2, "call_timeout": 5.0}
    to_thief = TeamSyncClient(f"http://{HOST}:{thief_port}/mcp", SECRET, **settings)
    to_police = TeamSyncClient(f"http://{HOST}:{police_port}/mcp", SECRET, **settings)
    return {
        "to_thief": to_thief,
        "to_police": to_police,
        "police_inboxes": police_inboxes,
        "thief_inboxes": thief_inboxes,
    }


@pytest.mark.slow
def test_an_ack_reaches_the_siblings_inbox(linked_pair):
    to_police = linked_pair["to_police"]

    reply = to_police.send_ack("series-1", "whatever-message-id", 1)

    assert reply["ok"] is True
    acked = linked_pair["police_inboxes"].acks.get(timeout=5.0)
    assert acked["series_id"] == "series-1"


@pytest.mark.slow
def test_a_subgame_result_arrives_in_the_polices_inbox(linked_pair):
    stub_result = {
        "series_id": "series-1",
        "sub_game_number": 2,
        "sender_role": "thief",
        "result": "capture",
    }

    to_police = linked_pair["to_police"]
    to_police._send_with_retry("subgame_result", stub_result)

    received = linked_pair["police_inboxes"].subgame_results.get(timeout=5.0)
    assert received["sub_game_number"] == 2
    assert received["hmac"]  # the client signed it before sending


@pytest.mark.slow
def test_status_request_gets_a_signed_status_response(linked_pair):
    reply = linked_pair["to_thief"].send_status_request("series-1")

    assert reply["state"] == "waiting"
    assert reply["hmac"]  # status_request is answered inline, signed like any message


@pytest.mark.slow
def test_a_message_signed_with_the_wrong_secret_is_rejected_over_the_real_link():
    port = free_port()
    start_coordinator(HOST, port, "the-real-secret", lambda: {"state": "idle"})
    wrong_secret_client = TeamSyncClient(
        f"http://{HOST}:{port}/mcp",
        "an-impostor-secret",
        connect_timeout=5.0,
        retry_interval=0.1,
        call_timeout=3.0,
    )

    with pytest.raises(TransportError, match="invalid hmac"):
        wrong_secret_client._send_with_retry(
            "subgame_result", {"series_id": "series-1", "sub_game_number": 2}
        )


@pytest.mark.slow
def test_an_unreachable_sibling_raises_transport_error_after_the_deadline():
    unreachable = TeamSyncClient(
        "http://127.0.0.1:1/mcp", SECRET, connect_timeout=0.3, retry_interval=0.1, call_timeout=0.2
    )

    with pytest.raises(TransportError):
        unreachable.send_status_request("series-1")
