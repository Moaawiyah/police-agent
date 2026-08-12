"""Tests for the outbound transport: retry policy, inbox polling and draining.

These exercise the transport's decision-making without a network. The single
MCP call it wraps is replaced, so a test never depends on a socket, a port or
another process being up; the real HTTP path is covered by the two-port
integration test.
"""

import pytest

from police_agent.exceptions import TransportError
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import PeerInboxes

UNREACHABLE = "http://127.0.0.1:1/mcp"


def transport(**overrides) -> McpTransport:
    settings = {"connect_timeout": 0.05, "retry_interval": 0.01, "reply_timeout": 0.05}
    return McpTransport(UNREACHABLE, PeerInboxes(), **(settings | overrides))


class Recorder:
    """Stands in for the MCP call, recording what would have gone on the wire."""

    def __init__(self, failures: int = 0):
        self.calls: list[tuple[str, dict]] = []
        self._failures = failures

    def __call__(self, tool: str, arguments: dict, timeout: float | None = None) -> None:
        self.calls.append((tool, arguments))
        if len(self.calls) <= self._failures:
            raise OSError("connection refused")


class TestInboundDos:
    def test_the_property_delegates_to_the_shared_inboxes_instance(self):
        inboxes = PeerInboxes()
        link = McpTransport(UNREACHABLE, inboxes)

        assert link.inbound_dos is inboxes.inbound_dos


class TestRetryPolicy:
    def test_a_late_starting_opponent_is_retried_not_failed(self):
        # Two processes never start at the same instant; early refusals are normal.
        link = transport(connect_timeout=5.0)
        link._call = Recorder(failures=2)
        link.send_turn({"step": 1})
        assert len(link._call.calls) == 3

    def test_an_unreachable_opponent_eventually_raises_naming_the_url(self):
        link = transport()
        with pytest.raises(TransportError, match=f"unreachable at {UNREACHABLE}"):
            link.send_turn({"step": 1})

    def test_the_original_failure_is_kept_as_the_cause(self):
        link = transport()
        with pytest.raises(TransportError) as raised:
            link.send_turn({"step": 1})
        assert raised.value.__cause__ is not None


class TestOutboundCalls:
    @pytest.mark.parametrize(
        ("method", "tool", "key"),
        [("send_turn", "receive_turn", "message"), ("exchange_agreement", "negotiate", "message")],
    )
    def test_each_method_targets_the_opponents_matching_tool(self, method, tool, key):
        link = transport()
        link._call = Recorder()
        link._inboxes.agreements.put({"theirs": True})
        getattr(link, method)({"mine": True})
        assert link._call.calls == [(tool, {key: {"mine": True}})]

    def test_audit_is_sent_under_the_payload_argument(self):
        link = transport()
        link._call = Recorder()
        link.exchange_audit({"records": []})
        assert link._call.calls == [("submit_audit", {"payload": {"records": []}})]


class TestHandshake:
    def test_returns_the_agreement_that_arrived_in_my_inbox(self):
        link = transport()
        link._call = Recorder()
        link._inboxes.agreements.put({"group": "thief-team"})
        assert link.exchange_agreement({"group": "police-team"}) == {"group": "thief-team"}

    def test_a_silent_opponent_fails_the_handshake(self):
        link = transport()
        link._call = Recorder()
        with pytest.raises(TransportError, match="No agreement from the opponent"):
            link.exchange_agreement({"group": "police-team"})


class TestPolling:
    def test_poll_turn_returns_the_queued_turn(self):
        link = transport()
        link._inboxes.turns.put({"step": 4})
        assert link.poll_turn(timeout=0.05) == {"step": 4}

    def test_poll_turn_times_out_to_none_rather_than_raising(self):
        # An overdue turn is a game-level verdict, not a transport failure.
        assert transport().poll_turn(timeout=0.01) is None

    def test_poll_control_never_blocks(self):
        link = transport()
        assert link.poll_control() is None
        link._inboxes.controls.put({"kind": "quit"})
        assert link.poll_control() == {"kind": "quit"}


class TestAuditExchange:
    def test_their_reveal_is_read_even_when_my_send_failed(self):
        # The winner may exit the instant it has read its inbox, killing its
        # server mid-call -- their payload can still be sitting in mine.
        link = transport(audit_send_timeout=0.02)
        link._inboxes.audits.put({"sender": "thief"})
        assert link.exchange_audit({"sender": "police"}) == {"sender": "thief"}

    def test_a_departed_opponent_yields_none_instead_of_an_error(self):
        assert transport(audit_send_timeout=0.02).exchange_audit({"sender": "police"}) is None


class TestDrain:
    def test_stale_turns_controls_and_audits_go_but_agreements_stay(self):
        link = transport()
        for inbox, message in (
            (link._inboxes.turns, "turn"),
            (link._inboxes.controls, "control"),
            (link._inboxes.audits, "audit"),
            (link._inboxes.agreements, "agreement"),
        ):
            inbox.put({"stale": message})

        link.drain_inboxes()

        assert link._inboxes.turns.empty()
        assert link._inboxes.controls.empty()
        assert link._inboxes.audits.empty()
        assert link._inboxes.agreements.get_nowait() == {"stale": "agreement"}

    def test_draining_empty_inboxes_is_harmless(self):
        transport().drain_inboxes()
