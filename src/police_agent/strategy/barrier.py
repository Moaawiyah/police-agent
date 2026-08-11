"""When the police should spend a barrier, and where.

A barrier is expensive twice over: the quota is fixed for the whole sub-game,
and placing one costs the police its step for that turn (3.4). The policy walls
any turn a reachable placement genuinely takes an escape away from the believed
thief -- not just once it is already nearly cornered -- since every escape
removed narrows tomorrow's chase, and a barrier held back earns nothing. A wall
that removes no escape has to earn the turn by shrinking the thief's pocket
instead (`strategy/encirclement.py`).

This module owns *whether* to wall; `strategy/placement.py` owns *where*, and
the safety rules that make a placement legal to consider at all.

The decision is deterministic. Sealed moves are re-checked against the revealed
logs in the end-of-game audit, so a placement has to be recomputable from the
replayed state alone; a probabilistic "wall 15% of the time" placement would
not be, and would also be unable to explain itself when it walls nothing useful.
"""

from police_agent.constants import DELTAS, Cell, Direction
from police_agent.domain.actions import barrier
from police_agent.domain.own_state import OwnGameState
from police_agent.strategy.decision import Decision
from police_agent.strategy.encirclement import WIDE_REACH
from police_agent.strategy.placement import best_placement


def choose_barrier(
    state: OwnGameState,
    believed: Cell,
    barriers_max: int,
    has_evidence: bool = True,
    belief: list[tuple[Cell, float]] | None = None,
) -> Decision | None:
    """Return the barrier placement worth making this turn, or None to move instead.

    Two placements the board allows are deliberately never used. The cell
    underfoot is not walled: it would deny the police, for the rest of the game,
    the one cell it is certain to be standing on. Neither is the cell the police
    *believes* the thief occupies, even though a barrier there is a capture
    condition (Appendix He 46) -- the specification does not pin down how that
    is evaluated against a sealed, simultaneous move, and stepping onto the same
    cell is a capture attempt that costs no quota, so the ambiguous option is
    never the only one on offer.

    `has_evidence` guards against walling on the opening, unstarted belief: one
    diffuse() over a flat prior is not uniform (corner cells have fewer targets
    to spread into), so `believed` can land somewhere with a wallable escape
    before a single real scent reading has ever arrived. That is a diffusion
    artifact, not the thief -- so `choose_barrier` refuses until real evidence
    exists. `PoliceBrain` supplies this from the belief's own `has_scent()`;
    direct callers default to `True`, matching a known target in a unit test.

    `belief` is the top-K distribution the placement is weighed against. It
    defaults to all the weight on `believed`, so a caller holding a single
    known target gets exactly the single-target behaviour.

    `WIDE_REACH` is the one range gate left. Inside it a wall can still bear on
    the thief, either by taking an escape or by shrinking its pocket; past it
    the turn is better spent closing the gap.
    """
    if not has_evidence:
        return None
    if state.my_barriers >= barriers_max:
        return None
    if state.board.distance(state.position, believed) > WIDE_REACH:
        return None
    found = best_placement(
        state.board,
        state.position,
        state.barriers,
        believed,
        belief or [(believed, 1.0)],
    )
    if found is None:
        return None
    cell, takes_escape = found
    return Decision(
        barrier(direction_to(state.position, cell)), _rationale(cell, believed, takes_escape, state)
    )


def _rationale(cell: Cell, believed: Cell, takes_escape: bool, state: OwnGameState) -> str:
    """Plain text for the game log: which of the two things this wall achieved."""
    if takes_escape:
        left = len(state.board.legal_moves(believed, state.barriers | {cell}))
        return f"wall {cell}: leaves the believed thief at {believed} {left} step(s)"
    return f"seal {cell}: shrinks the pocket around the believed thief at {believed}"


def direction_to(origin: Cell, cell: Cell) -> Direction:
    """The direction from `origin` to an orthogonally adjacent `cell`."""
    delta = (cell[0] - origin[0], cell[1] - origin[1])
    for direction, step in DELTAS.items():
        if step == delta:
            return direction
    raise ValueError(f"{cell} is not orthogonally adjacent to {origin}")
