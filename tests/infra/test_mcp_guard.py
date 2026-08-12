"""Tests for real inbound enforcement, driven over FastMCP's in-memory client.

Rejections are raised server-side as InboundDosError (an McpError), but the
client only ever observes fastmcp's own wrapped fastmcp.exceptions.ToolError
-- confirmed empirically, not assumed -- so assertions here match what an
opponent's transport would actually see, not the server-side exception type.
"""

import contextlib

from fastmcp.exceptions import ToolError

from police_agent.constants import Role
from police_agent.infra.mcp_server import PeerInboxes, build_peer_server
from tests.infra.test_mcp_server import call_tool


def peer(dos_limit_per_minute: float = 30.0):
    inboxes = PeerInboxes(dos_limit_per_minute)
    return build_peer_server(Role.POLICE, inboxes), inboxes


class TestFloodRejection:
    def test_a_flood_of_receive_turn_calls_is_rejected_after_the_limit(self):
        app, inboxes = peer(dos_limit_per_minute=5)

        for step in range(5):
            assert call_tool(app, "receive_turn", {"message": {"step": step}}) == {"ok": True}
        try:
            call_tool(app, "receive_turn", {"message": {"step": 5}})
            raise AssertionError("the 6th call should have been rejected")
        except ToolError as exc:
            assert "inbound rate exceeded" in str(exc)

        assert inboxes.inbound_dos.tripped is True

    def test_legitimate_low_rate_traffic_across_all_four_tools_is_unaffected(self):
        app, inboxes = peer(dos_limit_per_minute=30)

        assert call_tool(app, "negotiate", {"message": {}}) == {"ok": True}
        assert call_tool(app, "receive_turn", {"message": {}}) == {"ok": True}
        assert call_tool(app, "submit_audit", {"payload": {}}) == {"ok": True}
        assert call_tool(app, "receive_control", {"message": {}}) == {"ok": True}

        assert inboxes.inbound_dos.tripped is False

    def test_a_flood_on_a_low_frequency_tool_trips_the_same_shared_counter(self):
        """One shared budget across all 4 tools, not a per-tool allowance --
        negotiate is called once a match, but a flood aimed at it must trip
        the same guard receive_turn would."""
        app, inboxes = peer(dos_limit_per_minute=3)

        for _ in range(3):
            call_tool(app, "negotiate", {"message": {}})
        try:
            call_tool(app, "negotiate", {"message": {}})
            raise AssertionError("flooding negotiate alone should still trip the guard")
        except ToolError:
            pass

        assert inboxes.inbound_dos.tripped is True

    def test_once_tripped_the_rejected_payload_never_reaches_the_inbox(self):
        app, inboxes = peer(dos_limit_per_minute=1)

        call_tool(app, "receive_turn", {"message": {"step": 1}})
        with contextlib.suppress(ToolError):
            call_tool(app, "receive_turn", {"message": {"step": 2}})

        assert inboxes.turns.qsize() == 1
        assert inboxes.turns.get_nowait()["step"] == 1
