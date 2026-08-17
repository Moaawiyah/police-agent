"""Movement, barrier, and capture-response checks for semantic audit."""

from police_agent.constants import Direction
from police_agent.domain.semantic_records import cell

HOLD_TOKENS = frozenset({"", "-", "STAY", "HOLD"})
# A stay move has no agreed spelling, only an agreed *effect*. The binding
# parameter table fixes the vocabulary -- move_set = ["N","S","E","W","STAY"] --
# and leaves each team to render it: we send bare "STAY" (the book reference's
# form), our own general form is "HOLD:-", and najamjad's thief sends
# "MOVE:STAY", treating STAY as the move_set token it literally is. All three
# are conformant. A checker that accepts only its own spelling reads an honest
# opponent's hold as an illegal move and forfeits a game nobody tampered with,
# which is exactly what happened to sub-games 1/3/5 of MOAAMOHA-vs-najamjad.
# So the spelling is read leniently and the effect -- the position must not
# change -- is still enforced strictly.


def is_hold(move) -> bool:
    """Whether `move` is any conformant spelling of a stay."""
    if not isinstance(move, str):
        return False
    head, _, tail = move.strip().upper().partition(":")
    return head in {"STAY", "HOLD"} or (head == "MOVE" and tail.strip() in HOLD_TOKENS)


def thief_move(step, payload, origin, position, barriers, board, failures):
    """Check one revealed thief step against the board rules, appending to `failures` on mismatch."""
    move = payload.get("move")
    if is_hold(move):
        if position != origin:
            failures.append(f"turn {step} hold changes position")
        return
    if not isinstance(move, str) or not move.startswith("MOVE:"):
        failures.append(f"turn {step} has an illegal thief action")
        return
    if _move_target(board, origin, move.removeprefix("MOVE:"), barriers) != position:
        failures.append(f"turn {step} has an illegal move")


def police_turn(step, payload, logged, origin, barriers, board, failures):
    """Check one revealed police step against the local log and board rules.

    Returns the position and any barrier this step actually placed, for the
    caller to fold into the next step's `origin`/`barriers`.
    """
    position = cell(payload.get("position"))
    if position is None or not board.in_bounds(position):
        failures.append(f"local turn {step} has an out-of-bounds position")
        position = origin
    _match_local_log(step, payload, logged, failures)
    move = payload.get("move")
    placed = cell(payload.get("barrier")) if payload.get("barrier") is not None else None
    if is_hold(move):
        if position != origin or placed is not None:
            failures.append(f"local turn {step} has an illegal hold")
    elif isinstance(move, str) and move.startswith("MOVE:"):
        if (
            _move_target(board, origin, move.removeprefix("MOVE:"), barriers) != position
            or placed is not None
        ):
            failures.append(f"local turn {step} has an illegal move")
    elif isinstance(move, str) and move.startswith("BARRIER:"):
        target = origin if move == "BARRIER:-" else _move_target(board, origin, move[8:], barriers)
        if (
            position != origin
            or placed != target
            or target not in board.barrier_targets(origin, barriers)
        ):
            failures.append(f"local turn {step} has an illegal barrier")
    else:
        failures.append(f"local turn {step} has an unknown action")
    return position, placed


def claim_response(step, message, local_by_step, positions, failures):
    """Check a capture-claim response against the claim it answers and the true positions."""
    response = message.get("claim_response")
    if response is None:
        return
    if not isinstance(response, dict) or not isinstance(response.get("caught"), bool):
        failures.append(f"turn {step} has a malformed capture response")
        return
    claim = local_by_step.get(step - 1, {}).get("capture_claim")
    if claim is None:
        failures.append(f"turn {step} answers a capture claim that was never made")
        return
    if response.get("claim") != claim:
        failures.append(f"turn {step} does not echo the capture claim it answers")
    target, position = cell(claim), positions.get(step - 1)
    if target is None or position is None:
        failures.append(f"turn {step} cannot verify its capture response")
    elif response["caught"] != (target == position):
        failures.append(f"turn {step} gives a false capture response")


def _match_local_log(step, payload, logged, failures):
    if logged is None:
        failures.append(f"local turn {step} is absent from the move log")
    elif any(logged.get(key) != payload.get(key) for key in ("position", "move", "barrier")):
        failures.append(f"local turn {step} disagrees with its sealed record")


def _move_target(board, origin, direction, barriers):
    try:
        return board.step(origin, Direction(direction), barriers)
    except ValueError:
        return None
