"""When the police should spend a barrier, and where.

A barrier is expensive twice over: the quota is fixed for the whole sub-game,
and placing one costs the police its step for that turn (3.4). The policy walls
any turn a reachable placement genuinely takes an escape away from the believed
thief -- not just once it is already nearly cornered -- since every escape
removed narrows tomorrow's chase, and a barrier held back earns nothing.

The decision is deterministic. Sealed moves are re-checked against the revealed
logs in the end-of-game audit, so a placement has to be recomputable from the
replayed state alone; a probabilistic "wall 15% of the time" placement would
not be, and would also be unable to explain itself when it walls nothing useful.
"""

from police_agent.constants import DELTAS, Cell, Direction
from police_agent.domain.actions import barrier
from police_agent.domain.board import Board
from police_agent.domain.own_state import OwnGameState
from police_agent.strategy.decision import Decision

# A barrier can only ever touch the thief when the two are at most two cells
# apart: the police walls a cell one step from itself, and the thief steps one
# cell from where it stands. Past that a wall is geometrically incapable of
# taking anything away from it, so there is nothing to evaluate.
BARRIER_REACH = 2


def choose_barrier(
    state: OwnGameState, believed: Cell, barriers_max: int, has_evidence: bool = True
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
    """
    if not has_evidence:
        return None
    if state.my_barriers >= barriers_max:
        return None
    if state.board.distance(state.position, believed) > BARRIER_REACH:
        return None
    escapes = {target for _, target in state.board.legal_moves(believed, state.barriers)}
    if not escapes:
        return None
    cell = _best_placement(state, escapes)
    if cell is None:
        return None
    return Decision(
        barrier(direction_to(state.position, cell)),
        f"wall {cell}: leaves the believed thief at {believed} {len(escapes) - 1} step(s)",
    )


def _best_placement(state: OwnGameState, escapes: set[Cell]) -> Cell | None:
    """The first reachable cell that takes an escape away without trapping us.

    Candidates come from the board in its fixed N/S/E/W order, so the same state
    always yields the same placement. Any candidate that would leave the police
    with no legal step is rejected outright: 3.4 warns that a greedily placed
    barrier "may imprison the police itself behind the wall it built".
    """
    for cell in state.board.barrier_targets(state.position, state.barriers):
        if cell == state.position or cell not in escapes:
            continue
        if _would_confine(state.board, state.position, state.barriers | {cell}):
            continue
        return cell
    return None


def _would_confine(board: Board, position: Cell, barriers: set[Cell]) -> bool:
    """Whether `barriers` would leave `position` with no legal step.

    Asked of the board rather than of `OwnGameState.is_confined`, because the
    placement is still hypothetical here and the real state must not be touched
    to evaluate it.
    """
    return not board.legal_moves(position, barriers)


def direction_to(origin: Cell, cell: Cell) -> Direction:
    """The direction from `origin` to an orthogonally adjacent `cell`."""
    delta = (cell[0] - origin[0], cell[1] - origin[1])
    for direction, step in DELTAS.items():
        if step == delta:
            return direction
    raise ValueError(f"{cell} is not orthogonally adjacent to {origin}")
