"""The handshake works against a push peer AND a request/response peer.

Two conformant implementations can be mutually mute: one only ever pushes its
greeting to the other's server, the other only ever answers in its reply body.
These tests pin both halves of the fix -- what our negotiate hands back, and
which copy of the opponent's agreement `exchange_agreement` accepts.
"""

import asyncio

import pytest
from fastmcp import Client

from police_agent.constants import Role
from police_agent.exceptions import TransportError
from police_agent.infra import mcp_client_ops as ops
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_client_ops import exchange_agreement, greeting_in
from police_agent.infra.mcp_server import PeerInboxes, build_peer_server

UNREACHABLE = "http://127.0.0.1:1/mcp"
MINE = {"terms": {"grid": 7}, "nonce": "mine", "signature": "sig-mine", "identity": {}}
THEIRS = {"terms": {"grid": 7}, "nonce": "theirs", "signature": "sig-theirs", "identity": {}}


def call_negotiate(app, message: dict) -> dict:
    async def invoke() -> dict:
        async with Client(app) as client:
            return (await client.call_tool("negotiate", {"message": message})).data

    return asyncio.run(invoke())


def transport(inboxes: PeerInboxes | None = None) -> McpTransport:
    return McpTransport(
        UNREACHABLE,
        inboxes or PeerInboxes(),
        connect_timeout=0.05,
        retry_interval=0.01,
        reply_timeout=0.05,
    )


class TestNegotiateReply:
    """What our own server hands back to whoever called it."""

    def test_a_bare_acknowledgement_until_a_greeting_is_published(self):
        inboxes = PeerInboxes()
        app = build_peer_server(Role.POLICE, inboxes)
        assert call_negotiate(app, THEIRS) == {"ok": True}
        assert inboxes.agreements.get_nowait() == THEIRS

    def test_the_published_greeting_rides_in_the_reply(self):
        inboxes = PeerInboxes()
        inboxes.greeting = MINE
        app = build_peer_server(Role.POLICE, inboxes)
        assert call_negotiate(app, THEIRS) == {"ok": True, "message": MINE}

    def test_the_opponents_message_is_still_queued_when_a_greeting_is_published(self):
        """The reply is an addition, never a replacement for the inbox."""
        inboxes = PeerInboxes()
        inboxes.greeting = MINE
        app = build_peer_server(Role.POLICE, inboxes)
        call_negotiate(app, THEIRS)
        assert inboxes.agreements.get_nowait() == THEIRS


class TestGreetingIn:
    """An acknowledgement must never be mistaken for an agreement."""

    @pytest.mark.parametrize(
        "reply",
        [None, {}, {"ok": True}, {"message": None}, {"message": {"terms": {}}}, "not-a-dict"],
    )
    def test_anything_without_terms_and_nonce_is_not_a_greeting(self, reply):
        assert greeting_in(reply) is None

    def test_a_full_agreement_is_recognised(self):
        assert greeting_in({"ok": True, "message": THEIRS}) == THEIRS


class TestExchangeAgreement:
    """Which copy of the opponent's agreement we end up using."""

    def test_my_greeting_is_published_before_the_call_goes_out(self):
        inboxes = PeerInboxes()
        link = transport(inboxes)
        published: list = []
        link._send_with_retry = lambda *_a, **_k: published.append(inboxes.greeting) or {"ok": True}
        inboxes.agreements.put(THEIRS)
        exchange_agreement(link, MINE)
        assert published == [MINE]

    def test_a_reply_dialect_peer_is_read_from_the_reply(self):
        """Nothing is ever pushed to us, so the reply is the only copy."""
        link = transport()
        link._send_with_retry = lambda *_a, **_k: {"ok": True, "message": THEIRS}
        assert exchange_agreement(link, MINE) == THEIRS

    def test_a_push_dialect_peer_is_read_from_the_inbox(self):
        inboxes = PeerInboxes()
        link = transport(inboxes)
        link._send_with_retry = lambda *_a, **_k: {"ok": True}
        inboxes.agreements.put(THEIRS)
        assert exchange_agreement(link, MINE) == THEIRS

    def test_a_both_dialects_peer_leaves_no_duplicate_behind(self):
        """Otherwise the NEXT sub-game completes instantly against this stale copy."""
        inboxes = PeerInboxes()
        link = transport(inboxes)
        link._send_with_retry = lambda *_a, **_k: {"ok": True, "message": THEIRS}
        inboxes.agreements.put(THEIRS)
        assert exchange_agreement(link, MINE) == THEIRS
        assert inboxes.agreements.empty()

    def test_silence_from_both_paths_is_a_transport_error(self, monkeypatch):
        monkeypatch.setattr(ops, "NEGOTIATE_TIMEOUT_SECONDS", 0.05)
        link = transport()
        link._send_with_retry = lambda *_a, **_k: {"ok": True}
        with pytest.raises(TransportError, match="No agreement"):
            exchange_agreement(link, MINE)
