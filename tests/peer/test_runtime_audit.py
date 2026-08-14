"""Tamper detection and record sealing in the turn loop, split out of
test_runtime.py to keep both files under the project's line budget.
"""

from police_agent.domain.crypto import audit_records
from police_agent.domain.rules import TAMPER_FORFEIT
from police_agent.peer.protocol import AuditPayload
from police_agent.peer.step_zero import turn_records
from tests.peer.fake_transport import thief_turn, thief_turns
from tests.peer.runtime_helpers import run_against


def test_a_forged_opponent_log_forfeits_the_game():
    """A capture the police won is overridden when the thief's reveal will not hash."""
    forged = AuditPayload(
        sender="thief",
        records=[{"payload": {"step": 1}, "nonce": "n", "commit": "not-the-real-digest"}],
        result_claim="capture",
    ).to_dict()

    summary, _ = run_against(
        [thief_turn(1), thief_turn(2, claim_response={"caught": True})], audit=forged
    )

    assert (summary["result"], summary["winner"]) == (TAMPER_FORFEIT, "police")
    assert summary["audit"]["passed"] is False


def test_a_malformed_opponent_audit_forfeits_the_game():
    summary, _ = run_against(
        [thief_turn(1), thief_turn(2, claim_response={"caught": True})],
        audit={"sender": "thief"},
    )

    assert (summary["result"], summary["winner"]) == (TAMPER_FORFEIT, "police")
    assert summary["audit"]["semantic_failures"] == ["malformed audit reveal"]


def test_the_police_seals_one_record_per_turn_it_played():
    """Plus the step-zero declaration, which heads the log without being a turn."""
    summary, transport = run_against([thief_turn(1), thief_turn(2)])

    assert len(turn_records(summary["records"])) == len(transport.sent_turns) == 2
    assert all(record["commit"] for record in summary["records"])


def test_every_sealed_record_verifies_against_its_own_commit():
    """The audit this peer would face: its own log must survive it."""
    summary, _ = run_against(thief_turns(3))

    assert audit_records(summary["records"])["passed"] is True


def test_the_commit_on_the_wire_is_the_commit_of_the_record():
    summary, transport = run_against([thief_turn(1)])

    assert transport.sent_turns[0]["commit"] == turn_records(summary["records"])[0]["commit"]


def test_the_true_position_never_crosses_the_wire():
    _, transport = run_against(thief_turns(3))

    for message in transport.sent_turns:
        assert "position" not in message
        assert "nonce" not in message
