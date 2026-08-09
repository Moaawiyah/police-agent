"""Turning a completed turn into the two things it has to become.

Every turn produces a *sealed record* kept privately until the audit, and a
*wire message* sent immediately. They are built together, here, because the
commit in the message must be the commit of the record -- if those two ever came
from different payloads the audit would fail against an honest peer, which is a
far worse bug than an audit that fails against a dishonest one.

What goes into the sealed payload is the peer's true state: the position it will
not disclose, the move it made, the barrier it placed. That is exactly what the
audit needs in order to re-derive the game and check the claims made about it.
"""

from datetime import UTC, datetime

from police_agent.constants import Cell
from police_agent.domain.crypto import CommitReveal
from police_agent.domain.own_state import OwnGameState
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.reference_v3 import sealed_police_step


def now_iso() -> str:
    """A UTC timestamp. The specification requires one on every move."""
    return datetime.now(UTC).isoformat()


def _state_str(state: OwnGameState) -> str:
    """A compact, replayable rendering of the board as this peer sees it."""
    barriers = sorted([list(cell) for cell in state.barriers])
    return f"grid={state.board.size}x{state.board.size};self={list(state.position)};barriers={barriers}"


def sealed_step_record(
    state: OwnGameState,
    rationale: str,
    capture_claim: Cell | None,
    *,
    reference_v3: bool = False,
    hint: str = "",
) -> dict:
    """Seal one turn's truth: where I am, what I did, and what I claimed.

    The capture claim is inside the sealed payload as well as on the wire. That
    is what makes the claim binding: at the audit the thief can check that the
    cell the police *claimed* is the cell the police actually stood on, so a
    police peer cannot later deny a claim its opponent answered honestly.
    """
    if reference_v3:
        # Reference-v3 commits the StepIntent shape: the settled cell, the
        # explicit COP role, a wire move, intent, and the exact hint. The
        # capture claim remains a public protocol field and is intentionally
        # not part of that reference payload.
        return sealed_police_step(state, hint)

    last = state.log[-1] if state.log else {}
    payload = {
        "step": state.step_number,
        "state": _state_str(state),
        "position": list(state.position),
        "move": last.get("move", "-"),
        "barrier": last.get("barrier"),
        "unique_cells": state.unique_cells,
        "capture_claim": list(capture_claim) if capture_claim else None,
        "rationale": rationale,
    }
    return {"payload": payload, **CommitReveal.seal(payload)}


def build_turn_message(
    state: OwnGameState,
    commit: str,
    smell_grid: dict,
    hint: str = "",
    capture_claim: Cell | None = None,
    claim_response: dict | None = None,
) -> TurnMessage:
    """The public half of the same turn: a commitment, a trail, and a claim.

    The barrier is declared in the clear and unsealed, unlike everything else
    here. It has to be: a barrier is impassable for *both* peers (3.4), so an
    opponent that only learned about it at the audit could not have avoided it
    during the game.
    """
    placed = state.last_barrier()
    return TurnMessage(
        step=state.step_number,
        sender="police",
        hint=hint,
        smell_grid=smell_grid,
        commit=commit,
        timestamp=now_iso(),
        barrier_placed=list(placed) if placed else None,
        capture_claim=list(capture_claim) if capture_claim else None,
        claim_response=claim_response,
        win_claim=None,  # survival is the thief's claim to make, never the police's
    )
