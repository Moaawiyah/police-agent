"""`opponent_records` surviving from the audit into the filed summary.

A separate, small file rather than more cases in `test_runtime.py` -- that
file is already at the project's line budget, and this is one clearly scoped
behaviour (peer/summary.py's `exchange_and_audit`/`build_summary`).
"""

from police_agent.peer.protocol import AuditPayload
from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn


def run_against(incoming, audit=None, **overrides):
    """Play one sub-game against a scripted thief and return (summary, transport)."""
    transport = FakeTransport(incoming=incoming, audit=audit)
    summary = PoliceRuntime(config_with(**overrides), transport).run()
    return summary, transport


def test_opponent_records_survive_into_the_summary_even_when_the_audit_fails():
    """A tampered reveal is still filed, not discarded -- see summary.py's
    docstring: a team_sync import of the sibling role's settled result needs
    the opponent's revealed log, whether or not it passed verification."""
    forged = AuditPayload(
        sender="thief",
        records=[{"payload": {"step": 1}, "nonce": "n", "commit": "not-the-real-digest"}],
        result_claim="capture",
    ).to_dict()

    summary, _ = run_against(
        [thief_turn(1), thief_turn(2, claim_response={"caught": True})], audit=forged
    )

    assert summary["opponent_records"] == forged["records"]


def test_opponent_records_are_empty_when_the_opponent_never_reveals():
    summary, _ = run_against([thief_turn(1)])

    assert summary["opponent_records"] == []
