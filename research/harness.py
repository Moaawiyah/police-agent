"""One headless police-vs-evader episode, faithful to the shipped rules.

The turn order and the belief-update order are copied from the real runtime,
not re-invented, because a sweep run against a different game measures nothing:

* police decides and applies (`peer/turn_sender.py`), and a barrier it places
  is excluded from the posterior immediately;
* the evader moves and lays scent (`domain/scent.py`'s emit: decay, then
  deposit, then hand over the packet);
* the police folds the turn in -- `diffuse` first, then `observe_smell`
  (`peer/turn_handler.py:79`), because the message is proof the thief moved and
  the belief must spread before the fresh trail sharpens it again.

The three capture conditions match `domain/semantic_replay.py`: stepping onto
the evader's cell (only a MOVE is a claim, per `turn_sender.py:101`), walling
its cell (rule 46), and leaving it no legal step (rule 47).

Unlike the real police this harness is omniscient -- it has to be, since it
plays both sides to score the episode. The police *brain* still sees only the
posterior, which is the part being measured.
"""

import random
from dataclasses import dataclass

from police_agent.constants import MoveType
from police_agent.domain.board import Board
from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import CAPTURE, SURVIVAL, TIMEOUT
from police_agent.domain.scent import ScentField
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.brain import PoliceBrain
from research import (
    BOARD_SIZE,
    MAX_BARRIERS,
    MAX_STEPS,
    POLICE_START,
    SCENT_DECAY,
    SCENT_EMIT_INTENSITY,
    SCENT_GRID_SIZE,
    SCENT_MIN_CENTER,
    THIEF_START,
)
from research.evader import FLEE, SyntheticEvader


@dataclass(frozen=True)
class Episode:
    """What one episode produced. `steps` is the turn the game ended on."""

    result: str
    reason: str
    steps: int
    hits: int  # turns the posterior's argmax was the evader's real cell
    error_sum: int  # summed Manhattan error of the argmax
    prob_sum: float  # summed probability mass on the true cell

    @property
    def captured(self) -> bool:
        """Whether the police won this episode."""
        return self.result == CAPTURE

    @property
    def hit_rate(self) -> float:
        """Fraction of turns the posterior's argmax was correct."""
        return self.hits / self.steps if self.steps else 0.0

    @property
    def mean_error(self) -> float:
        """Mean Manhattan distance from the believed cell to the real one."""
        return self.error_sum / self.steps if self.steps else 0.0

    @property
    def mean_true_prob(self) -> float:
        """Mean posterior mass sitting on the evader's actual cell."""
        return self.prob_sum / self.steps if self.steps else 0.0


def play(seed: int, *, policy: str = FLEE, belief: dict | None = None) -> Episode:
    """Play one seeded episode and return its outcome and tracking metrics."""
    rng = random.Random(seed)
    board = Board(BOARD_SIZE)
    state = OwnGameState(POLICE_START, BOARD_SIZE)
    grid = BeliefGrid(BOARD_SIZE, **(belief or {}))
    scent = ScentField(
        BOARD_SIZE, SCENT_GRID_SIZE, SCENT_DECAY, SCENT_EMIT_INTENSITY, SCENT_MIN_CENTER
    )
    evader = SyntheticEvader(THIEF_START, board, policy, rng)
    brain = PoliceBrain(rng=rng)
    return _run(board, state, grid, scent, evader, brain)


def _run(board, state, grid, scent, evader, brain) -> Episode:
    """The turn loop itself, split out to keep `play` a readable set-up."""
    hits = error = 0
    prob = 0.0
    for step in range(1, MAX_STEPS + 1):
        decision = brain.decide(state, grid, MAX_BARRIERS)
        state.apply_move(decision.action, MAX_BARRIERS)
        placed = state.last_barrier()
        if placed is not None:
            grid.exclude(placed)
        ended = _terminal(decision, state, placed, evader, board, step)
        if ended is not None:
            return Episode(*ended, step, hits, error, prob)
        evader.step(state.position, state.barriers)
        grid.diffuse(state.barriers)
        grid.observe_smell(scent.emit(evader.position))
        believed = grid.most_likely()
        hits += believed == evader.position
        error += board.distance(believed, evader.position)
        prob += grid.as_matrix()[evader.position[0]][evader.position[1]]
    return Episode(SURVIVAL, "survival", MAX_STEPS, hits, error, prob)


def _terminal(decision, state, placed, evader, board, step) -> tuple[str, str] | None:
    """The three capture conditions, in the order `semantic_replay.py` checks them."""
    if decision.action.move_type is MoveType.MOVE and state.position == evader.position:
        return (CAPTURE, "claim")
    if placed is not None and placed == evader.position:
        return (CAPTURE, "barrier")
    if placed is not None and not board.legal_moves(evader.position, state.barriers):
        return (CAPTURE, "confinement")
    return None


def timeout_or_survival(episode: Episode, survival_threshold: int = MAX_STEPS) -> str:
    """Re-label a ceiling episode the way the agreed rules score it."""
    if episode.captured:
        return CAPTURE
    return SURVIVAL if episode.steps >= survival_threshold else TIMEOUT
