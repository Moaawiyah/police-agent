"""How the police chooses one turn's action.

Strategy is kept strictly downstream of the rules engine: nothing here decides
what is *legal*. Every candidate comes from `Board`, so the `Action` a brain
returns is always one `OwnGameState.apply_move` accepts, and when the police is
walled in the answer is HOLD rather than an illegal step. The domain layer never
imports this package, which is what stops a bad strategy from corrupting the
authoritative state -- it can only lose the game.

Two hooks stay open so a future policy can be swapped in by subclassing:

* `_pick_move(moves, state, threat)` -- choose among the legal single steps;
* `_decide_move(state, threat, barriers_max)` -- the whole turn, BARRIER included.

Movement tie-breaks are the one place this policy draws randomness: once
Manhattan distance and the unvisited-cell preference agree, every remaining
candidate is genuinely interchangeable, so choosing among them costs nothing
and stops the fixed N/S/E/W board order from silently deciding the chase.
Barrier placement stays fully deterministic (`strategy/barrier.py`) -- a wall
is a spent, irreversible resource and its choice must still be recomputable
from the replayed state alone. Movement is reproducible per seed instead: two
brains built with the same `random.Random` state always agree, so a saved
seed still reconstructs one specific game.
"""

import random

from police_agent.constants import Cell, Direction
from police_agent.domain.actions import hold, move
from police_agent.domain.own_state import OwnGameState
from police_agent.strategy.barrier import choose_barrier
from police_agent.strategy.decision import Decision
from police_agent.strategy.threat import ThreatEstimate

_NO_STEP = "no legal step remains"


class PoliceBrainBase:
    """The police decision policy. Override one of the two hooks to replace it."""

    def __init__(self, rng: random.Random | None = None) -> None:
        # PoliceBrain draws from this only to break a genuine movement tie,
        # never to choose among moves that are not already equally good.
        # Accepting it here rather than seeding internally is what lets the
        # runtime hand every brain the same seed and reproduce one specific
        # game.
        self._rng = rng or random.Random()

    def decide(
        self,
        state: OwnGameState,
        threat: ThreatEstimate,
        barriers_max: int = 0,
    ) -> Decision:
        """Choose this turn's action. The result is always legal to apply."""
        return self._decide_move(state, threat, barriers_max)

    def _decide_move(
        self,
        state: OwnGameState,
        threat: ThreatEstimate,
        barriers_max: int,
    ) -> Decision:
        """Base policy: take the step `_pick_move` picks, or HOLD when walled in."""
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return Decision(hold(), _NO_STEP)
        direction, target = self._pick_move(moves, state, threat)
        return Decision(move(direction), f"step {direction.value} to {target}")

    def _pick_move(
        self,
        moves: list[tuple[Direction, Cell]],
        state: OwnGameState,
        threat: ThreatEstimate,
    ) -> tuple[Direction, Cell]:
        """Pick one of the legal `(direction, target)` steps. `moves` is never empty."""
        raise NotImplementedError


class PoliceBrain(PoliceBrainBase):
    """Chase the believed thief cell, and wall only when a wall strictly helps."""

    def _decide_move(
        self,
        state: OwnGameState,
        threat: ThreatEstimate,
        barriers_max: int,
    ) -> Decision:
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return Decision(hold(), _NO_STEP)
        believed = threat.most_likely()
        wall = self._pick_barrier(state, believed, barriers_max, threat.has_scent())
        if wall is not None:
            return wall
        direction, target = self._pick_move(moves, state, threat)
        gap = state.board.distance(target, believed)
        return Decision(move(direction), f"chase {believed}: step {direction.value}, gap {gap}")

    def _pick_move(self, moves, state, threat):
        """Close the Manhattan gap to the believed cell, prefer unvisited ground
        on a tie, then pick randomly among whatever is still tied after that.

        Manhattan distance is the real number of moves away once diagonals are
        illegal, so minimising it minimises the remaining chase. Preferring an
        unvisited target on a tie costs nothing and pays twice: it widens the
        area the police has covered, and unique cells are what the scoring table
        credits. Anything still tied after both keys is genuinely
        interchangeable, so `self._rng.choice` costs no quality -- every option
        was already equally good -- and stops the board's fixed N/S/E/W order
        from silently becoming the real tie-break.
        """
        believed = threat.most_likely()

        def key(candidate: tuple[Direction, Cell]) -> tuple[int, bool]:
            return (state.board.distance(candidate[1], believed), candidate[1] in state.visited)

        best = min(key(m) for m in moves)
        tied = [m for m in moves if key(m) == best]
        return self._rng.choice(tied)

    def _pick_barrier(
        self,
        state: OwnGameState,
        believed: Cell,
        barriers_max: int,
        has_evidence: bool = True,
    ) -> Decision | None:
        """Delegate to the barrier policy. Override to change only the walling."""
        return choose_barrier(state, believed, barriers_max, has_evidence)
