"""The replay audit checks game meaning as well as commitment hashes."""

import pytest

from police_agent.domain.crypto import CommitReveal, audit_records
from police_agent.domain.rules import CAPTURE, SURVIVAL, GameRules
from police_agent.domain.semantic_audit import audit_semantics


def sealed(step, position, move, *, barrier=None, capture_claim=None):
    payload = {
        "step": step,
        "position": position,
        "move": move,
        "barrier": barrier,
        "capture_claim": capture_claim,
    }
    return {"payload": payload, **CommitReveal.seal(payload)}


def message(record, **fields):
    return {"step": record["payload"]["step"], "commit": record["commit"], **fields}


def audit(remote, messages, local, log, **kwargs):
    thief_start = kwargs.pop("thief_start", [3, 3])
    police_start = kwargs.pop("police_start", [0, 0])
    return audit_semantics(
        remote,
        messages,
        local,
        log,
        GameRules(4, 4),
        7,
        thief_start,
        police_start,
        **kwargs,
    )


def test_a_valid_revealed_history_passes_the_semantic_audit():
    remote = sealed(1, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S", capture_claim=[1, 0])

    result = audit([remote], [message(remote)], [local], [local["payload"]])

    assert audit_records([remote])["passed"] is True
    assert result["semantic_passed"] is True
    assert result["semantic_failures"] == []


@pytest.mark.parametrize(
    ("remote_position", "remote_move", "message_fields", "expected"),
    [
        ([3, 5], "MOVE:E", {}, "illegal move"),
        ([3, 3], "HOLD:-", {"win_claim": {"type": SURVIVAL}}, "early or invalid survival"),
    ],
)
def test_semantic_audit_rejects_false_claims_and_illegal_moves(
    remote_position, remote_move, message_fields, expected
):
    remote = sealed(1, remote_position, remote_move)
    local = sealed(1, [1, 0], "MOVE:S", capture_claim=[1, 0])

    result = audit([remote], [message(remote, **message_fields)], [local], [local["payload"]])

    assert result["semantic_passed"] is False
    assert any(expected in failure for failure in result["semantic_failures"])


def test_semantic_audit_rejects_a_forged_capture_response():
    one = sealed(1, [3, 3], "HOLD:-")
    two = sealed(2, [3, 3], "HOLD:-")
    local_one = sealed(1, [1, 0], "MOVE:S", capture_claim=[1, 0])
    local_two = sealed(2, [2, 0], "MOVE:S")
    response = {"claim": [1, 0], "caught": True}

    result = audit(
        [one, two],
        [message(one), message(two, claim_response=response)],
        [local_one, local_two],
        [local_one["payload"], local_two["payload"]],
    )

    assert result["semantic_passed"] is False
    assert any("false capture response" in failure for failure in result["semantic_failures"])


def test_semantic_audit_rejects_missing_or_duplicate_steps():
    one = sealed(1, [3, 3], "HOLD:-")
    three = sealed(3, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S")

    result = audit([one, three], [message(one), message(three)], [local], [local["payload"]])

    assert result["semantic_passed"] is False
    assert any("not contiguous" in failure for failure in result["semantic_failures"])


def test_barrier_capture_overrides_an_incorrect_reported_survival():
    remote = sealed(1, [0, 1], "HOLD:-")
    local = sealed(1, [0, 0], "BARRIER:E", barrier=[0, 1])

    result = audit(
        [remote],
        [message(remote)],
        [local],
        [local["payload"]],
        reported_result=SURVIVAL,
        thief_start=[0, 1],
    )

    assert result["semantic_passed"] is True
    assert result["terminal"] == {"result": CAPTURE, "winner": "police", "step": 1, "reason": "barrier"}
    assert result["semantic_corrections"] == ["reported survival overridden by barrier capture"]


def test_turns_after_a_barrier_capture_are_invalid():
    one = sealed(1, [0, 1], "HOLD:-")
    two = sealed(2, [0, 1], "HOLD:-")
    local = sealed(1, [0, 0], "BARRIER:E", barrier=[0, 1])

    result = audit(
        [one, two],
        [message(one), message(two)],
        [local],
        [local["payload"]],
        thief_start=[0, 1],
    )

    assert result["semantic_passed"] is False
    assert any("after barrier capture" in failure for failure in result["semantic_failures"])


def test_confinement_capture_overrides_an_incorrect_reported_survival():
    one = sealed(1, [0, 0], "HOLD:-")
    two = sealed(2, [0, 0], "HOLD:-")
    local_one = sealed(1, [0, 0], "BARRIER:S", barrier=[1, 0])
    local_two = sealed(2, [0, 0], "BARRIER:E", barrier=[0, 1])

    result = audit(
        [one, two],
        [message(one), message(two)],
        [local_one, local_two],
        [local_one["payload"], local_two["payload"]],
        reported_result=SURVIVAL,
        thief_start=[0, 0],
    )

    assert result["semantic_passed"] is True
    assert result["terminal"]["reason"] == "confinement"
    assert result["semantic_corrections"] == ["reported survival overridden by confinement capture"]
