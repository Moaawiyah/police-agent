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
    assert result["terminal"] == {
        "result": CAPTURE,
        "winner": "police",
        "step": 1,
        "reason": "barrier",
    }
    assert result["semantic_corrections"] == ["reported survival overridden by barrier capture"]


def test_a_harmless_turn_after_a_barrier_capture_is_a_correction_not_a_failure():
    """The thief holds no barrier list, so it cannot know a barrier just ended
    the sub-game and plays on. That is a peer not told yet, not tampering."""
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

    assert result["semantic_passed"] is True
    assert result["semantic_failures"] == []
    assert result["semantic_corrections"] == ["turn 2 after barrier capture: peer not told yet"]


def test_an_actually_illegal_turn_after_a_barrier_capture_still_fails():
    """The leniency is scoped to 'you didn't know it ended', not 'anything
    goes' -- an out-of-bounds position in the same trailing turn must still
    be caught, or the correction becomes a way to smuggle bad data past audit."""
    one = sealed(1, [0, 1], "HOLD:-")
    two = sealed(2, [99, 99], "HOLD:-")
    local = sealed(1, [0, 0], "BARRIER:E", barrier=[0, 1])

    result = audit(
        [one, two],
        [message(one), message(two)],
        [local],
        [local["payload"]],
        thief_start=[0, 1],
    )

    assert result["semantic_passed"] is False
    assert any("out-of-bounds position" in failure for failure in result["semantic_failures"])


def test_turns_after_a_survival_or_claim_terminal_are_still_invalid():
    """Leniency is scoped to terminals the thief cannot see. A survival or
    claim terminal is one it raised itself, so playing past it stays tampering."""
    remote = [sealed(step, [3, 3], "HOLD:-") for step in range(1, 6)]
    local = [sealed(step, [0, 0], "HOLD:-") for step in range(1, 6)]
    claims = [
        message(
            record, **({"win_claim": {"type": SURVIVAL}} if record["payload"]["step"] == 4 else {})
        )
        for record in remote
    ]

    result = audit(remote, claims, local, [record["payload"] for record in local])

    assert result["semantic_passed"] is False
    assert any("after survival" in failure for failure in result["semantic_failures"])


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
