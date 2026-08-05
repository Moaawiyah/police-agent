"""The Bayesian belief map: where the police thinks the thief is.

The police never observes the thief's cell (domain/rules.py). It has a decaying
scent grid once a turn, and from that maintains a distribution over the whole
board -- ch. 6.4's `b(s) = P(thief = s | observations)`.

Each turn is one step of a Bayes filter, in this order:

    diffuse()       predict -- the thief moved, so mass spreads to where it
                    could have gone, and the distribution gets less certain
    observe_smell() update -- the fresh scent multiplies the cells it favours,
                    and normalising turns the result back into a distribution

The order is the whole point of a filter: sharpening on an observation and
*then* blurring it would throw the evidence away in the turn it arrived.
`scale()` is that same update opened up for evidence that is not scent, which is
how `strategy/bluff.py` weighs the thief's hints.

Inference, not decision-making, and not the scent mechanism either. It answers
`most_likely()` and nothing above knows how, so it holds no opinion about
compass directions, landmarks or who is lying.
"""
from police_agent.constants import Cell

# The weight a scent reading carries against the prior. Not an agreed term: it
# is this peer's own judgement, so it lives in the private game.toml.
DEFAULT_SMELL_TRUST = 4.0

# Below this the distribution has collapsed rather than merely got small, and
# dividing through would amplify float noise into a confident answer.
_EPSILON = 1e-9


class BeliefGrid:
    """A probability distribution over the board for the thief's cell."""

    # Mass may only spread the way the thief may actually move. The agreed move
    # set is one orthogonal step or staying put (constants.py), so a diagonal
    # neighbour is two moves away and must not gain mass in one turn. The
    # reference makes this a flag to serve a diagonal variant too; here the
    # move set is fixed, so a flag never to be flipped is only a trap.
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
        trust = config.get("belief.smell_trust", DEFAULT_SMELL_TRUST)
        return cls(terms["board_size"], trust)

    def observe_smell(self, cells: dict | None) -> None:
        """Update on one scent grid: cells that smell get likelier, then renormalise.

        The likelihood is `1 + trust * intensity`, so a cell with no reading is
        left alone rather than ruled out: silence is not evidence of absence, and
        a trail this peer cannot smell is what a distant thief produces.

        Malformed entries are skipped -- the grid comes from another team's
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

    def scale(self, cells, factor: float) -> None:
        """Reweight a set of cells, then renormalise.

        The update step for evidence that did not arrive as scent. Which cells
        and how much is the caller's judgement; all this knows is that the
        result must still be a distribution.
        """
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
        """The argmax: the cell the chase heuristic above this will target.

        Ties break on the first cell in row-major order, so the same evidence
        always yields the same answer -- the strategy above is deterministic and
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
