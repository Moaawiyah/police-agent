"""Focused regression tests for the reference-v3 adapter."""

import hashlib
import json

from police_agent.constants import Direction
from police_agent.domain.own_state import OwnGameState
from police_agent.domain.scent import ScentField
from police_agent.peer.protocol import AuditPayload
from police_agent.peer.reference_v3 import (
    commit_of,
    refuse_turn,
    seal,
    sealed_police_step,
    verify,
)
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.sealing import sealed_step_record
from tests.conftest import SCENT_TERMS, config_with
from tests.peer.fake_transport import FakeTransport

REFERENCE_SHARED = {
    "pheromones": {
        "pheromone_kernel": "book_table",
        "pheromone_transmit_lag": 1,
    }
}


class ReferenceTransport(FakeTransport):
    """A reference-v3-shaped fake with a late terminal message."""

    dialect = "reference_v3"

    def __init__(self, incoming, audit, terminal):
        super().__init__(incoming=incoming, audit=audit)
        self._terminal = list(terminal)

    def drain_turns(self, timeout=0.0):
        terminal, self._terminal = self._terminal, []
        return terminal


def _reference_record(step: int, state=(3, 3)) -> dict:
    payload = {
        "step": step,
        "role": "THIEF",
        "state": list(state),
        "move": "MOVE:STAY",
        "intent": "truth",
        "hint": "You will not find me.",
    }
    return {"payload": payload, **seal(payload, nonce=f"{step:032x}")}


def _reference_turn(record: dict, **fields) -> dict:
    message = {
        "step": record["payload"]["step"],
        "sender": "thief",
        "hint": record["payload"]["hint"],
        "smell_grid": {},
        "commit": record["commit"],
        "timestamp": "2026-08-09T10:00:00+00:00",
        "barrier_placed": None,
        "capture_claim": None,
        "claim_response": None,
        "win_claim": None,
    }
    message.update(fields)
    return message


def test_reference_commit_inserts_nonce_into_the_hashed_json():
    payload = {"step": 1, "role": "COP", "state": [1, 0]}
    nonce = "n"
    expected = hashlib.sha256(
        json.dumps(
            {**payload, "nonce": nonce},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    assert commit_of(payload, nonce) == expected
    verify(payload, nonce, expected)


def test_police_step_record_is_reference_step_intent_shape():
    state = OwnGameState((0, 0), 7)
    from police_agent.domain.actions import move

    state.apply_move(move(Direction.S))
    record = sealed_step_record(
        state,
        "toward the strongest posterior",
        (1, 0),
        reference_v3=True,
        hint="The station lights are getting closer.",
    )

    assert record["payload"] == {
        "step": 1,
        "role": "COP",
        "state": [1, 0],
        "move": "MOVE:S",
        "intent": "truth",
        "hint": "The station lights are getting closer.",
    }
    verify(record["payload"], record["nonce"], record["commit"])
    assert sealed_police_step(state, record["payload"]["hint"])["commit"]


def test_reference_book_table_and_one_turn_lag_are_used_on_the_wire():
    scent = ScentField.from_terms(SCENT_TERMS, REFERENCE_SHARED, reference_v3=True)
    scent.seed((3, 3))

    first = scent.emit((3, 4))
    second = scent.emit((3, 5))

    assert first["3,3"] == 0.9
    assert first["1,1"] == 0.04
    assert second["3,4"] == 0.9
    assert (
        refuse_turn(
            {
                "step": 1,
                "sender": "police",
                "hint": "",
                "smell_grid": first,
                "commit": "0" * 64,
                "timestamp": "now",
            }
        )
        == ""
    )


def test_reference_survival_terminal_is_drained_without_an_extra_police_move():
    first = _reference_record(1)
    terminal = _reference_record(2)
    audit = AuditPayload(
        sender="thief",
        records=[first, terminal],
        result_claim="survival",
    ).to_dict()
    transport = ReferenceTransport(
        [_reference_turn(first, win_claim={"type": "survival"})],
        audit,
        [_reference_turn(terminal, win_claim={"type": "survival"})],
    )

    summary = PoliceRuntime(
        config_with(rules__max_steps=1, rules__survival_threshold=1), transport
    ).run()

    assert (summary["result"], summary["winner"]) == ("survival", "thief")
    assert transport.sent_turns == []
    assert summary["audit"]["passed"] is True
    assert summary["audit"]["semantic_passed"] is True
