"""The token accounting slice of the match summary, split out of `summary.py`
purely to keep that file under the project's line budget -- `_tokens` has no
dependency on the rest of the summary and nothing else in this repo calls it.
"""


def tokens_of(runtime, audit: dict) -> dict:
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
