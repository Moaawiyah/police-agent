"""Tests for the peer-to-peer wire format: round-tripping and rejecting bad payloads."""

import pytest

from police_agent.exceptions import ProtocolError
from police_agent.peer.protocol import AuditPayload, ControlMessage, TurnMessage


def turn(**overrides) -> TurnMessage:
    fields = {
        "step": 3,
        "sender": "police",
        "hint": "I am near the park",
        "smell_grid": {"2,3": 0.9},
        "commit": "0" * 64,
        "timestamp": "2026-08-02T10:00:00",
    }
    return TurnMessage(**(fields | overrides))


class TestTurnMessage:
    def test_round_trips_through_a_dict(self):
        original = turn(barrier_placed=[1, 1], capture_claim=[2, 2])
        assert TurnMessage.from_dict(original.to_dict()) == original

    def test_optional_fields_default_to_absent(self):
        payload = turn().to_dict()
        assert payload["barrier_placed"] is None
        assert payload["win_claim"] is None

    def test_never_carries_the_sender_true_position(self):
        # Specification ch. 5: position/move/verdict stay sealed inside `commit`
        # until the end-of-game audit. A field named for them must not exist.
        payload = turn().to_dict()
        assert "position" not in payload
        assert "move" not in payload
        assert "nonce" not in payload

    def test_missing_required_field_is_a_protocol_error(self):
        payload = turn().to_dict()
        del payload["commit"]
        with pytest.raises(ProtocolError, match="missing required field"):
            TurnMessage.from_dict(payload)

    def test_error_names_every_missing_field(self):
        payload = turn().to_dict()
        del payload["step"]
        del payload["hint"]
        with pytest.raises(ProtocolError, match=r"\['hint', 'step'\]"):
            TurnMessage.from_dict(payload)

    def test_unknown_fields_are_ignored_for_interoperability(self):
        payload = turn().to_dict() | {"their_own_extension": 42}
        assert TurnMessage.from_dict(payload) == turn()

    @pytest.mark.parametrize("payload", ["not-a-dict", None, [1, 2, 3]])
    def test_non_object_payloads_are_rejected(self, payload):
        with pytest.raises(ProtocolError, match="must be an object"):
            TurnMessage.from_dict(payload)


class TestAuditPayload:
    def test_round_trips_through_a_dict(self):
        audit = AuditPayload(
            sender="police",
            records=[{"payload": {"step": 1}, "nonce": "abc", "commit": "def"}],
            result_claim="capture",
        )
        assert AuditPayload.from_dict(audit.to_dict()) == audit

    def test_an_audit_without_its_records_is_rejected(self):
        with pytest.raises(ProtocolError, match=r"missing required field\(s\): \['records'\]"):
            AuditPayload.from_dict({"sender": "thief", "result_claim": "survival"})


class TestControlMessage:
    def test_round_trips_and_defaults_are_advisory_only(self):
        control = ControlMessage(kind="status", sender="thief")
        assert ControlMessage.from_dict(control.to_dict()) == control
        assert control.sub_game_number == 1
        assert control.status == ""

    def test_tolerates_a_richer_control_message_from_another_implementation(self):
        decoded = ControlMessage.from_dict(
            {"kind": "restart", "sender": "thief", "step_budget": 2.5, "status": "PAUSED"}
        )
        assert decoded == ControlMessage(kind="restart", sender="thief", status="PAUSED")

    def test_kind_is_required(self):
        with pytest.raises(ProtocolError, match=r"\['kind'\]"):
            ControlMessage.from_dict({"sender": "thief"})
