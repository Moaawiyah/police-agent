"""The Bayesian belief map: where the police thinks the thief is.

The police never observes the thief's cell (domain/rules.py). What it has is a
decaying scent grid arriving once a turn, and from that it maintains a
probability distribution over the whole board -- the belief map of the book's
chapter 6.4, `b(s) = P(thief = s | observations)`.

Each turn is one step of a Bayes filter, in this order:

    diffuse()       predict -- the thief moved, so mass spreads to where it
                    could have gone, and the distribution gets less certain
    observe_smell() update -- the fresh scent multiplies the cells it favours,
                    and normalising turns the result back into a distribution

That ordering is the whole point of a filter and is not interchangeable:
sharpening on an observation and *then* blurring it would throw away the
evidence in the same turn it arrived.

This is inference, not decision-making, and it is not the scent mechanism
either. It answers `most_likely()` and nothing above it knows how that answer
was reached -- `strategy/brain.py` minimises Manhattan distance to the cell this
returns, which is the "Bayes + Manhattan" pairing the book recommends (6.3.1).
Ported from the course reference implementation.
"""

from police_agent.constants import Cell

# The weight a scent reading carries against the prior. Higher trusts the grid
# more and concentrates the belief faster. It is *not* an agreed term: it is
# this peer's own reading of an opponent it has no reason to trust, so it stays
# in the private game.toml and never reaches the handshake.
DEFAULT_SMELL_TRUST = 4.0

# Below this the distribution is treated as having collapsed rather than merely
# being small, and dividing through by it would amplify float noise into a
# confident answer.
_EPSILON = 1e-9


class BeliefGrid:
    """A probability distribution over the board for the thief's cell."""

    # Mass may only spread the way the thief may actually move. The agreed move
    # set is a single orthogonal step or staying put (constants.py), so a
    # diagonal neighbour is two moves away and must not receive mass in one
    # turn. The reference makes this a constructor flag because it also serves a
    # diagonal variant; here the move set is fixed by specification, so a flag
    # that must never be flipped would only be somewhere to make a mistake.
    _OFFSETS = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))

    def __init__(self, board_size: int, smell_trust: float = DEFAULT_SMELL_TRUST) -> None:
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        self._size = board_size
        self._smell_trust = smell_trust
        # Knowing nothing is a flat prior, not a guess: before any scent has
        # arrived every cell is equally likely.
        uniform = 1.0 / (board_size * board_size)
        self._probs = [[uniform] * board_size for _ in range(board_size)]

    @classmethod
    def from_config(cls, terms: dict, config) -> "BeliefGrid":
        """Board size from the signed terms; trust from this peer's private file."""
        return cls(
            terms["board_size"],
            smell_trust=config.get("belief.smell_trust", DEFAULT_SMELL_TRUST),
        )

    def observe_smell(self, cells: dict | None) -> None:
        """Update on one scent grid: cells that smell get likelier, then renormalise.

        The likelihood is `1 + trust * intensity`, so a cell with no reading is
        left alone rather than ruled out. Silence is not evidence of absence --
        a trail this peer cannot smell is exactly what a thief that has kept its
        distance produces.

        Malformed entries are skipped: the grid comes from another team's
        implementation, and one bad key is no reason to lose a playable match.
        """
        for key, value in (cells or {}).items():
            cell = self._parse(key)
            if cell is not None and isinstance(value, int | float):
                self._probs[cell[0]][cell[1]] *= 1.0 + self._smell_trust * float(value)
        self._normalize()

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

    def exclude(self, cell: Cell) -> None:
        """Rule a cell out entirely -- something proved the thief is not standing there."""
        if self._in_bounds(cell):
            self._probs[cell[0]][cell[1]] = 0.0
            self._normalize()

    def most_likely(self) -> Cell:
        """The argmax: the single cell the chase heuristic above this will target.

        Ties break on the first cell in row-major order, so the same evidence
        always yields the same answer. The strategy above is deterministic and
        would quietly stop being so if its input were not.
        """
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
