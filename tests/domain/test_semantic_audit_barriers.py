"""Barrier- and confinement-capture overrides of a false reported survival,
split out of test_semantic_audit.py to keep both files under the project's
line budget.
"""

from police_agent.domain.rules import CAPTURE, SURVIVAL
from tests.domain.test_semantic_audit import audit, message, sealed


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
