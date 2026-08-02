"""The end of a sub-game: exchange reveals, check them, report what happened.

The audit is the only point in the whole protocol where a peer learns the
opponent's true positions, and it happens after the result is already decided --
which is what makes it safe to reveal them.

A failed audit overrides the board result. That asymmetry is deliberate: a peer
that forged its log has already shown the board result cannot be trusted, so
winning on it would reward exactly the behaviour the commitments exist to
prevent.
"""

import time

from police_agent.domain.crypto import audit_records
from police_agent.domain.rules import TAMPER_FORFEIT, TECHNICAL_LOSS
from police_agent.peer.protocol import AuditPayload

SKIPPED_AUDIT = {"passed": False, "verified_steps": 0, "failed_steps": [], "skipped": True}

# Results where there is nobody left to audit with: the opponent already went
# silent, so asking it to reveal would only stall this peer for another timeout.
NO_AUDIT_RESULTS = (TECHNICAL_LOSS,)


def exchange_and_audit(runtime, result: str, winner: str | None) -> tuple[str, str | None, dict]:
    """Trade sealed logs with the opponent and re-verify theirs."""
    if result in NO_AUDIT_RESULTS:
        return result, winner, SKIPPED_AUDIT

    mine = AuditPayload(sender="police", records=runtime.records, result_claim=result)
    theirs = runtime.transport.exchange_audit(mine.to_dict())
    if theirs is None:
        # Our reveal may well have landed; theirs never came. Nothing is proven
        # either way, so the board result stands and the report says so.
        return result, winner, SKIPPED_AUDIT

    audit = audit_records(AuditPayload.from_dict(theirs).records)
    if not audit["passed"]:
        return TAMPER_FORFEIT, "police", audit
    return result, winner, audit


def build_summary(runtime, result: str, winner: str | None, audit: dict) -> dict:
    """The match record: the result, the evidence for it, and the logs behind it.

    Both peers' logs are included so the replay and the report can be rebuilt
    from this one object without re-running the game.
    """
    return {
        "result": result,
        "winner": winner,
        "role": "police",
        "steps": runtime.state.step_number,
        "unique_cells": runtime.state.unique_cells,
        "barriers_used": runtime.state.my_barriers,
        "started_at": runtime.started_at,
        "duration_seconds": round(time.monotonic() - runtime.started_monotonic, 1),
        "group_name": runtime.config.get("game.group_name", "unnamed"),
        "peer_identity": runtime.peer_identity,
        "audit": audit,
        "disputes": runtime.disputes,
        "records": runtime.records,
        "history": runtime.handler.history,
        "my_log": runtime.state.log,
    }
