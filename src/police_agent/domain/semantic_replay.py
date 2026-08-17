"""Chronological replay for the semantic audit."""

from police_agent.domain.board import Board
from police_agent.domain.rules import CAPTURE, SURVIVAL, TIMEOUT
from police_agent.domain.semantic_moves import claim_response, police_turn, thief_move
from police_agent.domain.semantic_records import (
    cell,
    check_local_coverage,
    match_messages,
    messages,
    result,
    split_trailing_claim,
    turns,
)


def replay_audit(
    revealed_records,
    received_messages,
    local_records,
    local_move_log,
    rules,
    board_size,
    thief_start,
    police_start,
    reported_result,
):
    """Replay remote moves followed by the corresponding police action."""
    failures: list[str] = []
    corrections: list[str] = []
    board = Board(board_size)
    thief, police = cell(thief_start), cell(police_start)
    if thief is None or police is None or not board.in_bounds(thief) or not board.in_bounds(police):
        return result(["agreed starting positions are invalid"], corrections, None)
    remote, local = (
        turns(revealed_records, "revealed", failures),
        turns(local_records, "local", failures),
    )
    received_messages, trailing_claim = split_trailing_claim(remote, received_messages)
    received = messages(received_messages, failures)
    match_messages(remote, received, failures)
    local_by_step = {step: payload for step, payload, _ in local}
    log_by_step = {
        entry["step"]: entry
        for entry in local_move_log or []
        if isinstance(entry, dict) and isinstance(entry.get("step"), int)
    }
    if len(log_by_step) != len(local_move_log or []):
        failures.append("local move log is missing an integer step")
    barriers: set[tuple[int, int]] = set()
    positions: dict[int, tuple[int, int]] = {}
    terminal = None
    for index, (step, payload, _) in enumerate(remote):
        _after_terminal(step, terminal, failures, corrections)
        position = cell(payload.get("position"))
        if position is None or not board.in_bounds(position):
            failures.append(f"turn {step} has an out-of-bounds position")
            position = thief
        thief_move(step, payload, thief, position, barriers, board, failures)
        thief, positions[step] = position, position
        message = received[index][1] if index < len(received) else {}
        if message.get("barrier_placed") is not None:
            failures.append(f"turn {step} declares a thief barrier")
        claim_response(step, message, local_by_step, positions, failures)
        terminal = _survival(step, message, rules, terminal, failures)
        if (record := local_by_step.get(step)) is not None:
            police, placed = police_turn(
                step, record, log_by_step.get(step), police, barriers, board, failures
            )
            terminal = _barrier_capture(step, placed, thief, barriers, board, terminal)
        response = message.get("claim_response")
        if isinstance(response, dict) and response.get("caught") and terminal is None:
            terminal = {"result": CAPTURE, "winner": "police", "step": step, "reason": "claim"}
    if terminal is None and trailing_claim is not None:
        claim_step, claim_message = trailing_claim
        before = len(failures)
        # Same validator as the in-band case (echoes the real claim, on the real
        # cell) -- just fed the one message that never opened a sealed step of
        # its own, so it answers as if it had (claim_step + 1, looked up via -1).
        claim_response(claim_step + 1, claim_message, local_by_step, positions, failures)
        if len(failures) == before:
            terminal = {
                "result": CAPTURE,
                "winner": "police",
                "step": claim_step,
                "reason": "claim",
            }
    check_local_coverage(local, log_by_step, failures)
    expected = terminal or _ceiling_result(local, rules)
    _check_reported(expected, reported_result, corrections, failures)
    return result(failures, corrections, expected)


def _after_terminal(step, terminal, failures, corrections):
    """Flag a turn after the game ended -- unless it's one the thief could not
    have known about (barrier/confinement, decided by police's own record),
    which is a correction, not tampering. Every other check in the loop still
    runs on the turn regardless; only this complaint is relaxed."""
    if terminal is None:
        return
    ended_by = "survival" if terminal["reason"] == "survival" else f"{terminal['reason']} capture"
    if terminal["reason"] in {"barrier", "confinement"}:
        corrections.append(f"turn {step} after {ended_by}: peer not told yet")
    else:
        failures.append(f"turn {step} occurs after {ended_by}")


def _survival(step, message, rules, terminal, failures):
    claim = message.get("win_claim")
    if not claim:
        return terminal
    if claim.get("type") != SURVIVAL or not rules.thief_survived(step):
        failures.append(f"turn {step} makes an early or invalid survival claim")
    elif terminal is None:
        return {"result": SURVIVAL, "winner": "thief", "step": step, "reason": "survival"}
    return terminal


def _barrier_capture(step, placed, thief, barriers, board, terminal):
    if placed is None:
        return terminal
    barriers.add(placed)
    if terminal is None and placed == thief:
        return {"result": CAPTURE, "winner": "police", "step": step, "reason": "barrier"}
    if terminal is None and not board.legal_moves(thief, barriers):
        return {"result": CAPTURE, "winner": "police", "step": step, "reason": "confinement"}
    return terminal


def _ceiling_result(local, rules):
    if not local or local[-1][0] < rules.max_steps:
        return None
    game_result = SURVIVAL if rules.thief_survived(local[-1][0]) else TIMEOUT
    return {
        "result": game_result,
        "winner": "thief" if game_result == SURVIVAL else None,
        "step": local[-1][0],
        "reason": "ceiling",
    }


def _check_reported(expected, reported, corrections, failures):
    if expected is None or reported is None or expected["result"] == reported:
        return
    if expected["reason"] in {"barrier", "confinement"}:
        corrections.append(f"reported {reported} overridden by {expected['reason']} capture")
    else:
        failures.append(f"reported outcome {reported} does not match {expected['result']}")
