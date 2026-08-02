"""Tests for this peer's inbound mailbox, driven over FastMCP's in-memory client.

No socket is bound here: build_peer_server returns the app unstarted, so the
tools can be exercised exactly as the opponent would call them, but in-process.
"""

import asyncio
import socket

import pytest
from fastmcp import Client

from police_agent.constants import Role
from police_agent.exceptions import ConfigError
from police_agent.infra.mcp_server import PeerInboxes, _ensure_port_free, build_peer_server


def call_tool(app, tool: str, arguments: dict) -> dict:
    """Invoke one tool the way the opponent's transport would, and return its reply."""

    async def invoke() -> dict:
        async with Client(app) as client:
            return (await client.call_tool(tool, arguments)).data

    return asyncio.run(invoke())


@pytest.fixture
def peer():
    inboxes = PeerInboxes()
    return build_peer_server(Role.POLICE, inboxes), inboxes


class TestInboxes:
    def test_every_conversation_starts_empty(self):
        inboxes = PeerInboxes()
        assert inboxes.agreements.empty()
        assert inboxes.turns.empty()
        assert inboxes.audits.empty()
        assert inboxes.controls.empty()


class TestReceiveTools:
    def test_server_exposes_exactly_the_four_receive_tools(self, peer):
        app, _ = peer

        async def names() -> set[str]:
            async with Client(app) as client:
                return {tool.name for tool in await client.list_tools()}

        assert asyncio.run(names()) == {
            "negotiate",
            "receive_turn",
            "submit_audit",
            "receive_control",
        }

    @pytest.mark.parametrize(
        ("tool", "key", "inbox"),
        [
            ("negotiate", "message", "agreements"),
            ("receive_turn", "message", "turns"),
            ("submit_audit", "payload", "audits"),
            ("receive_control", "message", "controls"),
        ],
    )
    def test_each_tool_lands_its_payload_in_its_own_inbox(self, peer, tool, key, inbox):
        app, inboxes = peer
        payload = {"marker": tool}

        assert call_tool(app, tool, {key: payload}) == {"ok": True}

        assert getattr(inboxes, inbox).get_nowait() == payload
        for other in ("agreements", "turns", "audits", "controls"):
            assert other == inbox or getattr(inboxes, other).empty()

    def test_payloads_are_stored_verbatim_and_in_order(self, peer):
        # The tools must not interpret the wire format: parsing belongs to the
        # game loop, which needs the raw dict to verify commits later.
        app, inboxes = peer
        for step in (1, 2):
            call_tool(app, "receive_turn", {"message": {"step": step, "commit": "x"}})
        assert [inboxes.turns.get_nowait()["step"] for _ in range(2)] == [1, 2]


class TestPortGuard:
    def test_a_free_port_passes(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        _ensure_port_free("127.0.0.1", port)  # no raise once the socket is closed

    def test_a_bound_port_is_refused_with_recovery_instructions(self):
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            port = taken.getsockname()[1]
            with pytest.raises(ConfigError, match=f"Port {port} on 127.0.0.1 is already in use"):
                _ensure_port_free("127.0.0.1", port)
