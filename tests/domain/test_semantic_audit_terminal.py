"""The thief's capture confirmation can arrive as an extra, unrecorded
terminal message -- it never opens a new sealed step, so it has no
counterpart in the thief's revealed `records`. The semantic audit must
recognise that one specific, legitimate mismatch instead of treating every
capture as tampered evidence (regression for the false `tamper_forfeit` a
real match produced once the terminal message stopped being silently
dropped as a replay).
"""

from police_agent.domain.crypto import CommitReveal, audit_records
from police_agent.domain.rules import CAPTURE, GameRules
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
        remote, messages, local, log, GameRules(4, 4), 7, thief_start, police_start, **kwargs
    )


def test_a_trailing_capture_confirmation_passes_the_audit():
    remote = sealed(1, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S", capture_claim=[3, 3])
    terminal = {"step": 1, "claim_response": {"claim": [3, 3], "caught": True}}

    result = audit([remote], [message(remote), terminal], [local], [local["payload"]])

    assert audit_records([remote])["passed"] is True
    assert result["semantic_passed"] is True
    assert result["terminal"] == {"result": CAPTURE, "winner": "police", "step": 1, "reason": "claim"}


def test_the_terminal_message_needs_no_commit_of_its_own():
    """The terminal notification was never in the sealed chain, so its wire
    commit (fresh, unlinked) plays no part in `match_messages` at all."""
    remote = sealed(1, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S", capture_claim=[3, 3])
    terminal = {
        "step": 1,
        "commit": "ff" * 32,
        "claim_response": {"claim": [3, 3], "caught": True},
    }

    result = audit([remote], [message(remote), terminal], [local], [local["payload"]])

    assert result["semantic_passed"] is True


def test_a_false_trailing_claim_still_fails_the_audit():
    """`caught: True` alone does not buy a pass -- it must also be true."""
    remote = sealed(1, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S", capture_claim=[1, 1])
    terminal = {"step": 1, "claim_response": {"claim": [1, 1], "caught": True}}

    result = audit([remote], [message(remote), terminal], [local], [local["payload"]])

    assert result["semantic_passed"] is False
    assert any("false capture response" in failure for failure in result["semantic_failures"])


def test_a_trailing_message_that_is_not_a_genuine_capture_is_still_flagged():
    """A caught: False extra message is not the one legitimate exception, so
    the ordinary count-mismatch failure still applies."""
    remote = sealed(1, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S", capture_claim=[3, 3])
    extra = {"step": 1, "claim_response": {"claim": [3, 3], "caught": False}}

    result = audit([remote], [message(remote), extra], [local], [local["payload"]])

    assert result["semantic_passed"] is False
    assert any("count does not match" in failure for failure in result["semantic_failures"])


def test_an_unrelated_extra_message_is_still_flagged():
    remote = sealed(1, [3, 3], "HOLD:-")
    local = sealed(1, [1, 0], "MOVE:S")
    extra = {"step": 1, "hint": "surprise"}

    result = audit([remote], [message(remote), extra], [local], [local["payload"]])

    assert result["semantic_passed"] is False
    assert any("count does not match" in failure for failure in result["semantic_failures"])
