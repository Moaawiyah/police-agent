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
from police_agent.domain.rules import ABORTED, CAPTURE, TAMPER_FORFEIT, TECHNICAL_LOSS
from police_agent.domain.semantic_audit import audit_semantics
from police_agent.exceptions import ProtocolError
from police_agent.peer.handshake import identity_from_config
from police_agent.peer.protocol import AuditPayload
from police_agent.peer.sealing import now_iso
from police_agent.peer.step_zero import step_zero_of

SKIPPED_AUDIT = {
    "passed": False,
    "verified_steps": 0,
    "failed_steps": [],
    "semantic_passed": False,
    "semantic_failures": ["audit was not exchanged"],
    "skipped": True,
    "peer_tokens_total": 0,
}

# Results where there is nobody left to audit with, so asking for a reveal would
# only stall this peer for another timeout: the opponent already went silent, or
# -- having been stopped from the GUI -- this peer is the one that walked away.
NO_AUDIT_RESULTS = (TECHNICAL_LOSS, ABORTED)


def exchange_and_audit(runtime, result: str, winner: str | None) -> tuple[str, str | None, dict]:
    """Trade sealed logs with the opponent and re-verify theirs."""
    if result in NO_AUDIT_RESULTS:
        return result, winner, SKIPPED_AUDIT

    mine = AuditPayload(sender="police", records=runtime.records, result_claim=result)
    theirs = runtime.transport.exchange_audit(mine.to_dict())
    if theirs is None:
        audit = {**SKIPPED_AUDIT, "semantic_failures": ["opponent did not reveal its audit"]}
        return TECHNICAL_LOSS, "police", audit
    try:
        revealed = AuditPayload.from_dict(theirs)
    except (ProtocolError, TypeError, ValueError, KeyError):
        audit = {**SKIPPED_AUDIT, "skipped": False, "semantic_failures": ["malformed audit reveal"]}
        return TAMPER_FORFEIT, "police", audit
    audit = audit_records(revealed.records)
    audit.update(
        audit_semantics(
            revealed.records,
            runtime.handler.history,
            runtime.records,
            runtime.state.log,
            runtime.rules,
            runtime.terms["board_size"],
            runtime.terms["thief_start"],
            runtime.terms["cop_start"],
            revealed.result_claim,
        )
    )
    if not audit["passed"] or not audit["semantic_passed"]:
        return TAMPER_FORFEIT, "police", audit
    terminal = audit.get("terminal")
    if (
        terminal
        and terminal["result"] == CAPTURE
        and terminal["reason"] in {"barrier", "confinement"}
    ):
        return CAPTURE, "police", audit
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
        "ended_at": now_iso(),
        "duration_seconds": round(time.monotonic() - runtime.started_monotonic, 1),
        "group_name": runtime.config.get("game.group_name", "unnamed"),
        "peer_identity": runtime.peer_identity,
        # The four report artifacts (ch. 9.3.3) are rebuilt from this file alone,
        # and they need what was agreed, who we said we were, and what we
        # declared before moving -- none of which is derivable from the turns.
        "terms": runtime.terms,
        "identity": identity_from_config(runtime.config, runtime.records[0]["commit"]),
        "step_zero": step_zero_of(runtime.records),
        "audit": audit,
        # How far the thief's words survived contact with its own scent trail.
        # Below 0.5 is a peer that talked its way into being disbelieved.
        "opponent_reliability": round(runtime.analyst.reliability, 3),
        "tokens": _tokens(runtime, audit),
        # Evidence that the rate limiter was in the path, not merely present:
        # the counters say how many outbound calls it admitted, queued, retried
        # and refused, and `inbound_dos` reports how hard the opponent pushed.
        "gatekeeper": runtime.gatekeeper.snapshot(),
        "inbound_dos": runtime.inbound_dos.snapshot(),
        "hint_readings": runtime.handler.readings,
        "disputes": runtime.disputes,
        "records": runtime.records,
        "history": runtime.handler.history,
        "my_log": runtime.state.log,
        # Per-step scent grid + Bayesian posterior (police-only): what the
        # belief filter saw and concluded at each update, for analysis and for
        # a faithful (rather than merely re-derived) replay.
        "belief_log": runtime.belief_log,
    }


def _tokens(runtime, audit: dict) -> dict:
    """What this sub-game consumed, against the series budget (Appendix He 54).

    The series total is deliberately absent rather than guessed: a sub-game runs
    in its own process and cannot see its siblings' spend. It is the sum of
    `tokens_total` across the series' summaries, which is a figure the report can
    add up from files it has -- unlike one this peer would have to invent.

    `peer_tokens_total` is the opponent's own figure: `audit_records()` sums it
    from the peer's revealed, tamper-checked payloads, so it is 0 whenever the
    peer's schema omits `tokens` or the audit did not pass -- an unverified
    reveal proves nothing about spend.
    """
    trusted = audit.get("passed")
    return {
        **runtime.tokens.snapshot(),
        "budget_per_series": runtime.config.get("game.token_budget_per_series"),
        "peer_tokens_total": int(audit.get("peer_tokens_total") or 0) if trusted else 0,
    }
