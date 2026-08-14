"""The Bayesian belief map: where the police thinks the thief is.

The police never observes the thief's cell (domain/rules.py); each turn it `diffuse()`s (mass
spreads, thief moved) then `observe_smell()`s (fresh readings multiply favoured cells,
normalising restores a distribution) -- ch. 6.4's `b(s) = P(thief = s | observations)`.
That order matters: sharpening then blurring would throw evidence away the turn it
arrived. `scale()` opens the same update to non-scent evidence (`strategy/bluff.py`).
Inference only, holding no opinion about directions or who is lying.

Split across three companion files to stay under the project's line budget,
each following the same convention -- functions take the grid as their first
argument and reach into its private state exactly as a bound method would,
the pattern `infra/mcp_client_ops.py` uses for `McpTransport`:

- `belief_defaults.py` -- the tuning constants, re-exported below.
- `belief_update.py` -- `observe_smell`'s evidence pipeline.
- `belief_queries.py` -- the read-side (`scale`, `exclude`, `most_likely`,
  `top_cells`, `as_matrix`, `has_scent`).
"""

from police_agent.constants import Cell
from police_agent.strategy import belief_queries as queries
from police_agent.strategy import belief_update as update
from police_agent.strategy.belief_defaults import (
    DEFAULT_LEAK,
    DEFAULT_SMELL_POWER,
    DEFAULT_SMELL_TRUST,
    DEFAULT_STALE_DECAY,
    DEFAULT_STALE_SUPPORT,
)
from police_agent.strategy.belief_defaults import (
    EPSILON as _EPSILON,
)


class BeliefGrid:
    """A probability distribution over the board for the thief's cell."""

    # One orthogonal step or staying put -- a diagonal is two moves away (constants.py).
    _OFFSETS = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))

    def __init__(
        self,
        board_size: int,
        smell_trust: float = DEFAULT_SMELL_TRUST,
        smell_power: float = DEFAULT_SMELL_POWER,
        leak: float = DEFAULT_LEAK,
        stale_decay: float = DEFAULT_STALE_DECAY,
        stale_support: float = DEFAULT_STALE_SUPPORT,
    ) -> None:
        """A flat prior over `board_size` cells, tuned by the five constants above."""
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        self._size = board_size
        self._smell_trust = smell_trust
        self._smell_power = smell_power
        self._leak = leak
        self._stale_decay = stale_decay
        self._stale_support = stale_support
        self._observed = False  # real evidence vs. an unstarted, still-uniform prior
        uniform = 1.0 / (board_size * board_size)  # flat prior: nothing known yet
        self._probs = [[uniform] * board_size for _ in range(board_size)]

    @classmethod
    def from_config(cls, terms: dict, config) -> "BeliefGrid":
        """Board size from the signed terms; trust/power/leak/staleness from this peer's own file."""
        trust = config.get("belief.smell_trust", DEFAULT_SMELL_TRUST)
        power = config.get("belief.smell_power", DEFAULT_SMELL_POWER)
        leak = config.get("belief.leak", DEFAULT_LEAK)
        stale_decay = config.get("belief.stale_decay", DEFAULT_STALE_DECAY)
        stale_support = config.get("belief.stale_support", DEFAULT_STALE_SUPPORT)
        return cls(terms["board_size"], trust, power, leak, stale_decay, stale_support)

    def observe_smell(self, cells: dict | None) -> None:
        """Fold a scent reading into the posterior; see `belief_update.py` for the pipeline."""
        update.observe_smell(self, cells)

    def _shrink_unsupported(self, supported: set) -> None:
        update._shrink_unsupported(self, supported)

    def diffuse(self, barriers: set[Cell] | None = None) -> None:
        """Predict: spread mass over reach; a barrier target is skipped -- impassable."""
        blocked = barriers or set()
        fresh = [[0.0] * self._size for _ in range(self._size)]
        for row in range(self._size):
            for col in range(self._size):
                mass = self._probs[row][col]
                if mass < _EPSILON:
                    continue  # a ruled-out cell has nothing to spread
                targets = [
                    (row + d_row, col + d_col)
                    for d_row, d_col in self._OFFSETS
                    if self._in_bounds((row + d_row, col + d_col))
                    and (row + d_row, col + d_col) not in blocked
                ]
                if not targets:
                    targets = [(row, col)]  # walled in on every side: mass stays put
                share = mass / len(targets)
                for target_row, target_col in targets:
                    fresh[target_row][target_col] += share
        self._probs = fresh
        self._normalize()

    def scale(self, cells, factor: float) -> None:
        """Reweight cells for non-scent evidence, then renormalise -- caller's judgement."""
        queries.scale(self, cells, factor)

    def exclude(self, cell: Cell) -> None:
        """Rule a cell out entirely -- something proved the thief is not standing there."""
        queries.exclude(self, cell)

    def most_likely(self) -> Cell:
        """The argmax; ties break row-major so the same evidence always answers the same."""
        return queries.most_likely(self)

    def top_cells(self, count: int = 1) -> list[tuple[Cell, float]]:
        """The `count` likeliest cells and their probabilities, likeliest first."""
        return queries.top_cells(self, count)

    def as_matrix(self) -> list[list[float]]:
        """A copy of the distribution, for the heatmap and the game log."""
        return queries.as_matrix(self)

    def has_scent(self) -> bool:
        """Whether any real scent evidence has been observed yet."""
        return queries.has_scent(self)

    def _normalize(self) -> None:
        total = sum(sum(row) for row in self._probs)
        if total < _EPSILON:
            uniform = 1.0 / (self._size * self._size)
            self._probs = [[uniform] * self._size for _ in range(self._size)]
            return
        self._probs = [[prob / total for prob in row] for row in self._probs]

    def _in_bounds(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self._size and 0 <= cell[1] < self._size

    def _parse(self, key: str) -> Cell | None:
        """Turn a `"row,col"` wire key into an on-board cell, or None."""
        try:
            row_text, col_text = str(key).split(",")
            cell = (int(row_text), int(col_text))
        except ValueError:
            return None
        return cell if self._in_bounds(cell) else None
