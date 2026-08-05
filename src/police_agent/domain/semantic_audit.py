"""Public entry point for semantic end-of-game audit verification."""

from police_agent.domain.rules import GameRules
from police_agent.domain.semantic_replay import replay_audit


def audit_semantics(
    revealed_records: list[dict],
    received_messages: list[dict],
    local_records: list[dict],
    local_move_log: list[dict],
    rules: GameRules,
    board_size: int,
    thief_start: list[int] | tuple[int, int],
    police_start: list[int] | tuple[int, int],
    reported_result: str | None = None,
) -> dict:
    """Replay both logs and return semantic audit status without mutating them.

    ``received_messages`` is the accepted on-wire thief history; ``local_*``
    supplies the police's sealed, public barrier history.  ``reported_result``
    is optional so independent callers can verify a log without a summary.
    """
    return replay_audit(
        revealed_records,
        received_messages,
        local_records,
        local_move_log,
        rules,
        board_size,
        thief_start,
        police_start,
        reported_result,
    )
