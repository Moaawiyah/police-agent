"""The police runtime playing a real match over real MCP sockets.

Everything below the test is the production path: the runtime, the transport,
two FastMCP servers, two ports. Only the opponent is scripted, and it is
scripted at the wire -- it speaks the protocol rather than importing anything of
ours, which is what makes this a rehearsal for the thief repository rather than
a test of ourselves talking to ourselves.
"""

import socket
import threading

import pytest

from police_agent.constants import Role
from police_agent.domain.crypto import CommitReveal
from police_agent.domain.rules import CAPTURE
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import start_peer_server
from police_agent.peer.handshake import Negotiation
from police_agent.peer.protocol import AuditPayload
from police_agent.peer.terms import validate_agreement
from tests.conftest import config_with
from tests.peer.fake_transport import thief_turn

HOST = "127.0.0.1"
SETTINGS = {"connect_timeout": 20.0, "retry_interval": 0.2, "reply_timeout": 20.0}


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def _sealed_thief_turn(step, position) -> dict:
    payload = {"step": step, "position": position, "move": "HOLD:-", "barrier": None}
    return {"payload": payload, **CommitReveal.seal(payload)}


def play_thief(transport, terms) -> dict:
    """The opponent's side of one short match, spoken entirely over the wire."""
    transport.exchange_agreement(Negotiation(terms, {"group_id": "thief-team"}).signed())

    # (0,6) is chosen so the scent and the uninformed prior disagree: the centre
    # prior sends the police S, this sends it E. The move proves which was used.
    first = _sealed_thief_turn(1, [0, 1])
    transport.send_turn(thief_turn(1, commit=first["commit"], smell_grid={"0,6": 0.9}))
    police_turn = transport.poll_turn(timeout=20.0)
    assert police_turn is not None, "the police never took its turn"

    # Concede the claim the police just made, which ends the game as a capture.
    second = _sealed_thief_turn(2, [0, 1])
    transport.send_turn(
        thief_turn(
            2,
            commit=second["commit"],
            claim_response={"claim": police_turn["capture_claim"], "caught": True},
        )
    )
    mine = AuditPayload(sender="thief", records=[first, second], result_claim=CAPTURE)
    return {"police_turn": police_turn, "audit": transport.exchange_audit(mine.to_dict())}


@pytest.mark.slow
def test_a_full_sub_game_over_two_real_ports():
    from police_agent.peer.runtime import PoliceRuntime

    police_port, thief_port = free_port(), free_port()
    police_inboxes = start_peer_server(Role.POLICE, HOST, police_port)
    thief_inboxes = start_peer_server(Role.THIEF, HOST, thief_port)

    config = config_with(positions__thief_start=[0, 1])
    police_transport = McpTransport(f"http://{HOST}:{thief_port}/mcp", police_inboxes, **SETTINGS)
    thief_transport = McpTransport(f"http://{HOST}:{police_port}/mcp", thief_inboxes, **SETTINGS)

    results: dict = {}
    threads = [
        threading.Thread(
            target=lambda: results.update(police=PoliceRuntime(config, police_transport).run()),
            daemon=True,
        ),
        threading.Thread(
            target=lambda: results.update(
                thief=play_thief(thief_transport, validate_agreement(config))
            ),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive(), "the distributed match did not finish"

    summary = results["police"]
    assert (summary["result"], summary["winner"]) == (CAPTURE, "police")
    assert summary["peer_identity"]["group_id"] == "thief-team"

    # The police chased the scent it was actually sent, not its uninformed prior:
    # the prior would have taken it S to (1,0), the scent takes it E to (0,1).
    assert results["thief"]["police_turn"]["capture_claim"] == [0, 1]
    assert summary["audit"]["passed"] is True
    assert summary["audit"]["semantic_passed"] is True
