"""The Bayesian belief map: where the police thinks the thief is.

The police never observes the thief's cell (domain/rules.py); each turn it
`diffuse()`s (mass spreads, thief moved) then `observe_smell()`s (fresh
readings multiply favoured cells, normalising restores a distribution) --
ch. 6.4's `b(s) = P(thief = s | observations)`. That order matters:
sharpening then blurring would throw evidence away the turn it arrived.
`scale()` opens the same update to non-scent evidence (`strategy/bluff.py`).

Inference only: it answers `most_likely()` and holds no opinion about
directions or who is lying.
"""
from police_agent.constants import Cell

# Weight a scent reading carries against the prior -- private judgement, lives
# in game.toml, not an agreed term.
DEFAULT_SMELL_TRUST = 4.0

# Convexity of the intensity->likelihood curve. Above 1, a faint stale trail
# cell is starved much harder than a fresh strong one -- linear barely tells
# the two apart, and the belief ends up shaped like the whole trail.
DEFAULT_SMELL_POWER = 2.0

# Sliver of the posterior re-mixed to uniform each observation. Consecutive
# scent readings are the same decaying trail sampled again, not independent
# evidence, so without this a cell stays overweighted after the thief leaves.
DEFAULT_LEAK = 0.03

# Below this the distribution has collapsed, not merely got small; dividing
# through would amplify float noise into a confident answer.
_EPSILON = 1e-9


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
    ) -> None:
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        self._size = board_size
        self._smell_trust = smell_trust
        self._smell_power = smell_power
        self._leak = leak
        uniform = 1.0 / (board_size * board_size)  # flat prior: nothing known yet
        self._probs = [[uniform] * board_size for _ in range(board_size)]

    @classmethod
    def from_config(cls, terms: dict, config) -> "BeliefGrid":
        """Board size from the signed terms; trust/power/leak from this peer's own file."""
        trust = config.get("belief.smell_trust", DEFAULT_SMELL_TRUST)
        power = config.get("belief.smell_power", DEFAULT_SMELL_POWER)
        leak = config.get("belief.leak", DEFAULT_LEAK)
        return cls(terms["board_size"], trust, power, leak)

    def observe_smell(self, cells: dict | None) -> None:
        """`1 + trust*intensity**power` per smelly cell, normalise, then leak
        toward uniform. No reading leaves a cell alone, not ruled out -- silence
        is not evidence of absence. Malformed entries are skipped, not fatal."""
        for key, value in (cells or {}).items():
            cell = self._parse(key)
            if cell is not None and isinstance(value, int | float):
                boost = 1.0 + self._smell_trust * float(value) ** self._smell_power
                self._probs[cell[0]][cell[1]] *= boost
        self._normalize()
        self._leak_toward_uniform()

    def diffuse(self) -> None:
        """Predict: the thief moved one step, so spread each cell's mass over its reach."""
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
                ]
                share = mass / len(targets)
                for target_row, target_col in targets:
                    fresh[target_row][target_col] += share
        self._probs = fresh
        self._normalize()

    def scale(self, cells, factor: float) -> None:
        """Reweight cells for non-scent evidence, then renormalise -- caller's judgement."""
        for cell in cells:
            if self._in_bounds(cell):
                self._probs[cell[0]][cell[1]] *= factor
        self._normalize()

    def exclude(self, cell: Cell) -> None:
        """Rule a cell out entirely -- something proved the thief is not standing there."""
        if self._in_bounds(cell):
            self._probs[cell[0]][cell[1]] = 0.0
            self._normalize()

    def most_likely(self) -> Cell:
        """The argmax; ties break row-major so the same evidence always answers the same."""
        best, best_prob = (0, 0), -1.0
        for row in range(self._size):
            for col in range(self._size):
                if self._probs[row][col] > best_prob:
                    best, best_prob = (row, col), self._probs[row][col]
        return best

    def as_matrix(self) -> list[list[float]]:
        """A copy of the distribution, for the heatmap and the game log."""
        return [row[:] for row in self._probs]

    def _normalize(self) -> None:
        total = sum(sum(row) for row in self._probs)
        if total < _EPSILON:
            uniform = 1.0 / (self._size * self._size)
            self._probs = [[uniform] * self._size for _ in range(self._size)]
            return
        self._probs = [[prob / total for prob in row] for row in self._probs]

    def _leak_toward_uniform(self) -> None:
        """Only `observe_smell` calls this -- the others already normalise once
        per turn, and leaking there too would double it in one turn."""
        if self._leak <= 0.0:
            return
        uniform = 1.0 / (self._size * self._size)
        self._probs = [
            [(1.0 - self._leak) * prob + self._leak * uniform for prob in row]
            for row in self._probs
        ]

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
