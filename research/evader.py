"""A synthetic evader: the trajectory generator the sweeps run against.

NOT a thief agent, and deliberately too simple to be mistaken for one. It holds
no belief, reads no scent, sends no message and knows nothing about the
protocol; it exists only so a police policy has something to chase and a scent
trail has something to follow. CLAUDE.md keeps real thief logic in the other
repository, and this file stays outside `src/` so the boundary is visible.

Two behaviours, because a sweep that only ever measured one would not show
whether a result was about the police or about its opponent:

* `random` -- an unbiased walk. Measures raw localisation: the trail is the
  only signal, and no adversary is fighting the filter.
* `flee` -- greedily maximise Manhattan distance from the police's *actual*
  cell. Deliberately omniscient. That is the pessimistic case for the police,
  and a parameter that still helps under it is not winning by luck.
"""

import random

from police_agent.constants import Cell
from police_agent.domain.board import Board

RANDOM = "random"
FLEE = "flee"
POLICIES = (RANDOM, FLEE)


class SyntheticEvader:
    """A seeded walker on `board`, either unbiased or greedily fleeing."""

    def __init__(self, start: Cell, board: Board, policy: str, rng: random.Random) -> None:
        """Place the evader at `start`; `policy` is one of `POLICIES`."""
        if policy not in POLICIES:
            raise ValueError(f"policy must be one of {POLICIES}, got {policy!r}")
        self.position = start
        self._board = board
        self._policy = policy
        self._rng = rng

    def step(self, police: Cell, barriers: set[Cell]) -> Cell:
        """Take one turn's move and return the new position.

        Staying put is always an option, so a walled-in evader is never forced
        into an illegal move -- confinement is the police's win condition to
        earn (rule 47), not something this fixture should crash on.
        """
        options = [target for _, target in self._board.legal_moves(self.position, barriers)]
        options.append(self.position)  # STAY is a legal move for both sides
        if self._policy == RANDOM:
            self.position = self._rng.choice(options)
        else:
            self.position = self._furthest(options, police)
        return self.position

    def _furthest(self, options: list[Cell], police: Cell) -> Cell:
        """The option furthest from `police`, ties broken by the seeded RNG.

        Tie-breaking randomly rather than by list order keeps the board's fixed
        N/S/E/W ordering from quietly biasing every episode the same way.
        """
        best = max(self._board.distance(cell, police) for cell in options)
        return self._rng.choice([c for c in options if self._board.distance(c, police) == best])
