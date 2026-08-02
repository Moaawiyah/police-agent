"""Commit-reveal: sealing hides, revealing proves, tampering is caught."""

import pytest

from police_agent.domain.crypto import CommitReveal, audit_records
from police_agent.exceptions import CryptoError

PAYLOAD = {"step": 1, "position": [2, 3], "move": "MOVE:S"}


def test_a_sealed_payload_verifies_against_its_own_nonce():
    seal = CommitReveal.seal(PAYLOAD)

    CommitReveal.verify(PAYLOAD, seal["nonce"], seal["commit"])  # does not raise


def test_the_same_payload_seals_differently_every_time():
    """A repeated nonce would let an opponent recognise a repeated position."""
    first, second = CommitReveal.seal(PAYLOAD), CommitReveal.seal(PAYLOAD)

    assert first["nonce"] != second["nonce"]
    assert first["commit"] != second["commit"]


def test_key_order_does_not_change_the_commitment():
    """Two honest peers must hash the same bytes for the same facts."""
    reordered = {"move": "MOVE:S", "position": [2, 3], "step": 1}

    assert CommitReveal.commit_of(PAYLOAD, "n") == CommitReveal.commit_of(reordered, "n")


def test_changing_the_payload_after_sealing_is_caught():
    seal = CommitReveal.seal(PAYLOAD)
    rewritten = {**PAYLOAD, "position": [0, 0]}

    with pytest.raises(CryptoError, match="Commit mismatch"):
        CommitReveal.verify(rewritten, seal["nonce"], seal["commit"])


def test_a_wrong_nonce_is_caught():
    seal = CommitReveal.seal(PAYLOAD)

    with pytest.raises(CryptoError):
        CommitReveal.verify(PAYLOAD, "not-the-nonce", seal["commit"])


def test_an_honest_log_passes_the_audit():
    records = [{"payload": {"step": n}, **CommitReveal.seal({"step": n})} for n in range(3)]

    assert audit_records(records) == {"passed": True, "verified_steps": 3, "failed_steps": []}


def test_the_audit_names_every_failing_step_not_just_the_first():
    records = [{"payload": {"step": n}, **CommitReveal.seal({"step": n})} for n in range(4)]
    records[1]["commit"] = "forged"
    records[3]["commit"] = "forged"

    result = audit_records(records)

    assert result["passed"] is False
    assert result["failed_steps"] == [1, 3]
    assert result["verified_steps"] == 2


def test_an_incomplete_reveal_fails_rather_than_passes():
    """Omitting the nonce must not be a way to skip the audit for a step."""
    sealed = CommitReveal.seal({"step": 7})

    assert audit_records([{"payload": {"step": 7}, "commit": sealed["commit"]}])["passed"] is False
    assert audit_records([{"nonce": "n", "commit": "c"}])["passed"] is False


def test_an_empty_log_passes_vacuously():
    assert audit_records([])["passed"] is True
