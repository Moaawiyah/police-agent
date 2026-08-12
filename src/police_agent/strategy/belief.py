"""The Bayesian belief map: where the police thinks the thief is.

The police never observes the thief's cell (domain/rules.py); each turn it `diffuse()`s (mass
spreads, thief moved) then `observe_smell()`s (fresh readings multiply favoured cells,
normalising restores a distribution) -- ch. 6.4's `b(s) = P(thief = s | observations)`.
That order matters: sharpening then blurring would throw evidence away the turn it
arrived. `scale()` opens the same update to non-scent evidence (`strategy/bluff.py`).
Inference only, holding no opinion about directions or who is lying.

The read-side queries (`scale`, `exclude`, `most_likely`, `top_cells`, `as_matrix`,
`has_scent`) live in `belief_queries.py`, split out to keep this file -- the
update pipeline itself -- under the project's line budget. Each takes the grid
as its first argument and reaches back into its private state exactly as a
bound method would, the same pattern `infra/mcp_client_ops.py` uses.
"""

from police_agent.constants import Cell
from police_agent.strategy import belief_queries as queries

# Weight a scent reading carries against the prior -- private, lives in game.toml, not agreed.
DEFAULT_SMELL_TRUST = 4.0

# Convexity of intensity->likelihood curve; above 1 a faint (relative to this reading's own
# peak) cell is starved harder than a fresh one.
DEFAULT_SMELL_POWER = 3.0

# Sliver of the posterior re-mixed to uniform each observation. Consecutive scent readings
# are the same decaying trail sampled again -- without this a cell stays overweighted.
DEFAULT_LEAK = 0.03

# Extra multiplicative shrink applied, every observation, to any cell that did
# NOT clear the support bar this turn (see DEFAULT_STALE_SUPPORT). 1.0 disables
# it -- an unsupported cell is then untouched here, today's behaviour. A cell
# that stays unsupported for several turns in a row gets this applied each of
# those turns, so it compounds (stale_decay**n) with no separate counter needed
# -- repeatedly multiplying is the compounding. Kept as a direct shrink on the
# cell itself (not a change to _leak_toward_uniform's rate) so it rides the same
# single normalize() the boost step already relies on, rather than needing its
# own -- an earlier version that scaled the *leak rate* per cell instead broke
# leak's mass-conservation and, once renormalized, was pulling stale cells back
# UP through the same global rescale that repairs the total; this shrinks
# straight into the numerator, which normalize() then divides through cleanly.
# Swept on BeliefGrid(7): one strong hit at (3,3), then real evidence at a
# fixed far cell (0,0) every turn for 30 turns, reading the (0,0)/(3,3) ratio:
# 1.0->522, 0.9->596, 0.85->635, 0.8->675, 0.7->759, 0.5->947 -- monotonic and
# correctly signed at every point. 0.85 is a noticeable-but-not-extreme pick
# (+21.6% over disabled), not a round-number guess.
DEFAULT_STALE_DECAY = 0.85
# The reading (peak-relative within its own packet, same quantity smell_power
# shapes) a cell must clear to count as supported this turn. Below it, staleness
# still ages even though the wire packet lists the cell -- ScentField keeps a
# strong trail listed, if faintly, far longer than one turn, so "still in the
# packet" alone says little about freshness.
DEFAULT_STALE_SUPPORT = 0.1

# Below this the distribution has collapsed; dividing through would amplify float noise.
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
        """`1 + trust*reading**power` per smelly cell, where `reading` is that
        cell's intensity relative to THIS snapshot's own peak, not an absolute
        value -- a broadly faded field (lag, distance, time since deposit) still
        has a relatively freshest cell, and evidence should concentrate there,
        since an absolute reading would starve it for being dim overall. Then
        normalise and leak toward uniform. No reading rules a cell out -- silence
        is not evidence of absence. Malformed entries are skipped, not fatal."""
        parsed: dict = {}
        for key, value in (cells or {}).items():
            cell = self._parse(key)
            if cell is not None and isinstance(value, int | float):
                parsed[cell] = min(1.0, max(0.0, float(value)))  # negative here can turn complex
        peak = max(parsed.values(), default=0.0)
        supported: set = set()
        if peak > 0.0:
            for cell, intensity in parsed.items():
                reading = intensity / peak
                boost = 1.0 + self._smell_trust * reading**self._smell_power
                self._probs[cell[0]][cell[1]] *= boost
                self._observed = True
                if reading >= self._stale_support:
                    supported.add(cell)
        self._shrink_unsupported(supported)
        self._normalize()
        queries.leak_toward_uniform(self)

    def _shrink_unsupported(self, supported: set) -> None:
        """Every cell this reading didn't clear the support bar for loses a
        further stale_decay share of its mass -- silent, faint, or never
        touched alike. A cell unsupported N turns running gets this N times in
        a row, so the shrink compounds on its own; normalize() right after is
        what redistributes the freed mass, the same way it already absorbs the
        boost loop's non-conservation above."""
        if self._stale_decay >= 1.0:
            return
        for row in range(self._size):
            for col in range(self._size):
                if (row, col) not in supported:
                    self._probs[row][col] *= self._stale_decay

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
