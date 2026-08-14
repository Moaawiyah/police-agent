"""The pheromone field: what this peer smells of, and what it smells elsewhere.

The mechanism is mandatory and its three constants are fixed by the
specification (Appendix Vav, table 16: centre intensity, decay rate and field
size are marked *kavua*, and deviating from them disqualifies the group). They
arrive from the signed agreed terms; nothing here invents one.

This is the mechanism and nothing else. It knows how a trail is laid and how it
fades, and holds no opinion about where the thief is or where the police should
go -- that inference is `strategy/belief.py`, the decision `strategy/brain.py`.
Keeping the three apart is what stops a scent tweak becoming a strategy change.

The update law is the book's, ch. 4.3, `tau(t+1) = (1 - rho) * tau(t) +
delta_tau`, clamped at zero. Decay multiplies, so a trail thins towards nothing
without quite reaching it -- the long historical tail the chapter wants, still
legible twenty turns on. The course reference subtracts a flat 0.10 instead and
erases a trail in nine; it departs from the book in three places and this module
follows the book on all three (docs/TODO.md).

The merge/decay/wire-format side (`absorb`, `decay_all`, `snapshot`, key
parsing) lives in `scent_ops.py`, split out to keep this file -- laying and
reading a trail -- under the project's line budget.
"""

from police_agent.constants import Cell
from police_agent.domain import scent_ops as ops
from police_agent.domain.scent_kernel import emission_kernel


class ScentField:
    """One peer's view of the trail: cell intensities, laid and faded over time."""

    def __init__(
        self,
        board_size: int,
        grid_size: int,
        decay: float,
        emit_intensity: float,
        min_center: float,
    ) -> None:
        """An empty field over a `board_size` board, tuned by the four agreed constants."""
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        if grid_size < 1 or grid_size % 2 == 0:
            raise ValueError(f"Scent field size must be positive and odd, got {grid_size}")
        self._board_size = board_size
        self._grid_size = grid_size
        self._decay = decay
        self._emit_intensity = emit_intensity
        self._min_center = min_center
        self._values: dict[Cell, float] = {}

    @classmethod
    def from_terms(cls, terms: dict) -> "ScentField":
        """Build from the signed agreed terms, the only source for these constants."""
        return cls(
            terms["board_size"],
            terms["smell_grid_size"],
            terms["decay_per_step"],
            terms["emit_intensity"],
            terms["min_center_intensity"],
        )

    def emit(self, position: Cell) -> dict[str, float]:
        """Fade the old trail, lay a fresh one around `position`, and hand it over.

        Decay first, then deposit: the law adds `delta_tau` *after* the
        `(1 - rho)` factor, so a cell just stepped on carries full strength and
        only starts fading a turn later. Ch. 4.4 depends on it, reading last
        turn's trail as `(1 - rho) * 0.9 = 0.81`.
        """
        self.decay_all()
        self.deposit(position)
        return self.snapshot()

    def deposit(self, center: Cell, intensity: float | None = None) -> None:
        """Lay a fresh trail around `center`, keeping the stronger value per cell.

        The law is written `+ delta_tau`, and ch. 4.4 is what pins down what
        that means: the cell an agent left one turn ago reads 0.81, yet it sits
        one step from where the agent now stands and so takes a fresh 0.62 too.
        Keeping the stronger leaves 0.81; adding gives 1.43. So the `+` means
        refresh, not accumulate -- which is also what makes the stated
        [0, emit_intensity] range hold with no clamp to impose it.
        """
        if intensity is None:
            intensity = self._emit_intensity
        if intensity < self._min_center:
            raise ValueError(
                f"Centre intensity {intensity} is below the agreed minimum {self._min_center}"
            )
        for cell, value in self._radial(center, intensity).items():
            self._values[cell] = max(self._values.get(cell, 0.0), value)

    def absorb(self, cells: dict | None) -> None:
        """Merge a received `{"r,c": intensity}` grid into this field, max wins."""
        ops.absorb(self, cells)

    def decay_all(self) -> None:
        """One full turn of fading; see `scent_ops.py` for the update law."""
        ops.decay_all(self)

    def intensity_at(self, cell: Cell) -> float:
        """This cell's current trail strength, or 0.0 if it has none."""
        return self._values.get(cell, 0.0)

    def snapshot(self) -> dict[str, float]:
        """The wire form: `{"r,c": intensity}` for every cell that still smells."""
        return ops.snapshot(self)

    def _radial(self, center: Cell, intensity: float) -> dict[Cell, float]:
        """One emission landed on the board: the kernel translated and clipped."""
        emitted: dict[Cell, float] = {}
        for (d_row, d_col), value in emission_kernel(self._grid_size, intensity).items():
            cell = (center[0] + d_row, center[1] + d_col)
            if self._in_bounds(cell):
                emitted[cell] = value
        return emitted

    def _in_bounds(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self._board_size and 0 <= cell[1] < self._board_size

    def _parse(self, key: str) -> Cell | None:
        return ops.parse(self, key)
