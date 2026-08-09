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
"""

from police_agent.constants import Cell
from police_agent.domain.scent_kernel import emission_kernel, reference_emission_kernel

# Intensities cross the wire rounded to three decimals so both peers hold them
# identically. That rounding has a floor: multiply anything at or under 0.005 by
# 0.9 and it rounds back to itself, staining the board forever. Dropping below a
# hundredth clears the sticky region and still outlasts the agreed 35-move
# ceiling -- a full-strength trail only gets there after some forty turns.
_TRACE_FLOOR = 0.01


class ScentField:
    """One peer's view of the trail: cell intensities, laid and faded over time."""

    def __init__(
        self,
        board_size: int,
        grid_size: int,
        decay: float,
        emit_intensity: float,
        min_center: float,
        *,
        kernel: str | None = None,
        sigma_sq: float = 4.0 / 3.0,
        transmit_lag: int = 0,
    ) -> None:
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        if grid_size < 1 or grid_size % 2 == 0:
            raise ValueError(f"Scent field size must be positive and odd, got {grid_size}")
        self._board_size = board_size
        self._grid_size = grid_size
        self._decay = decay
        self._emit_intensity = emit_intensity
        self._min_center = min_center
        self._kernel = kernel
        self._sigma_sq = sigma_sq
        self._transmit_lag = max(0, int(transmit_lag))
        self._reference_v3 = kernel is not None or self._transmit_lag > 0
        self._values: dict[Cell, float] = {}
        self._history: list[dict[Cell, float]] = []

    @classmethod
    def from_terms(
        cls,
        terms: dict,
        shared: dict | None = None,
        *,
        reference_v3: bool | None = None,
    ) -> "ScentField":
        """Build from the signed agreed terms, the only source for these constants."""
        pheromones = (shared or {}).get("pheromones", {})
        kernel = terms.get("kernel", pheromones.get("pheromone_kernel"))
        sigma_sq = terms.get("sigma_sq", pheromones.get("pheromone_sigma_sq", 4.0 / 3.0))
        transmit_lag = terms.get("transmit_lag", pheromones.get("pheromone_transmit_lag", 0))
        if reference_v3 is False:
            kernel = None
            transmit_lag = 0
        return cls(
            terms["board_size"],
            terms["smell_grid_size"],
            terms["decay_per_step"],
            terms["emit_intensity"],
            terms["min_center_intensity"],
            kernel=kernel,
            sigma_sq=float(sigma_sq),
            transmit_lag=int(transmit_lag),
        )

    @property
    def reference_v3(self) -> bool:
        """Whether this field follows the reference table and lag semantics."""
        return self._reference_v3

    def seed(self, position: Cell) -> None:
        """Seed the opening emission used by reference-v3's lagged trail.

        The reference announces the start-cell trail on the first real move.
        It is public game configuration, so this does not disclose a new secret;
        it only makes the first broadcast deterministic on both sides.
        """
        if not self._reference_v3:
            return
        self.deposit(position)
        self._history = [dict(self._values)] if self._transmit_lag else []

    def emit(self, position: Cell) -> dict[str, float]:
        """Fade the old trail, lay a fresh one around `position`, and hand it over.

        Decay first, then deposit: the law adds `delta_tau` *after* the
        `(1 - rho)` factor, so a cell just stepped on carries full strength and
        only starts fading a turn later. Ch. 4.4 depends on it, reading last
        turn's trail as `(1 - rho) * 0.9 = 0.81`.
        """
        if self._reference_v3:
            self._record_before_emit()
            self.decay_all()
            self.deposit(position)
            return self.transmitted_snapshot()
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
            held = self._values.get(cell, 0.0)
            if self._reference_v3:
                self._values[cell] = min(self._emit_intensity, held + value)
            else:
                self._values[cell] = max(held, value)

    def absorb(self, cells: dict | None) -> None:
        """Merge a received `{"r,c": intensity}` grid into this field, max wins.

        Malformed entries are skipped, not raised on: the grid comes from
        another team's implementation, and forfeiting a match over one
        unparseable key would throw away a game still perfectly playable.
        Values are clamped to `[0, 1]` too -- a stray negative or oversized number
        should not be able to poison this peer's own view."""
        for key, value in (cells or {}).items():
            cell = self._parse(key)
            if cell is not None and isinstance(value, int | float):
                intensity = min(1.0, max(0.0, float(value)))
                self._values[cell] = max(self._values.get(cell, 0.0), intensity)

    def decay_all(self) -> None:
        """One full turn of fading: every trail keeps `1 - rho` of its strength.

        A cell loses a tenth of what it has, so it thins fast while strong and
        lingers once faint -- the historical shoulder the chapter asks for. Worn
        past the trace floor it is dropped rather than left as a stain.
        """
        if self._reference_v3:
            for cell in list(self._values):
                faded = max(0.0, self._values[cell] * (1.0 - self._decay))
                if faded < 1e-6:
                    del self._values[cell]
                else:
                    self._values[cell] = faded
            return
        for cell in list(self._values):
            faded = round(self._values[cell] * (1.0 - self._decay), 3)
            if faded >= _TRACE_FLOOR:
                self._values[cell] = faded
            else:
                del self._values[cell]

    def intensity_at(self, cell: Cell) -> float:
        return self._values.get(cell, 0.0)

    def snapshot(self) -> dict[str, float]:
        """The wire form: `{"r,c": intensity}` for every cell that still smells."""
        return {f"{row},{col}": value for (row, col), value in self._values.items() if value > 0.0}

    def transmitted_snapshot(self) -> dict[str, float]:
        """Return the live field or the reference-v3 lagged field for the wire."""
        if not self._reference_v3 or self._transmit_lag <= 0:
            return self.snapshot()
        values = self._history[0] if self._history else {}
        return {
            f"{row},{col}": round(value, 6)
            for (row, col), value in sorted(values.items())
            if value > 0.0
        }

    def _radial(self, center: Cell, intensity: float) -> dict[Cell, float]:
        """One emission landed on the board: the kernel translated and clipped."""
        emitted: dict[Cell, float] = {}
        kernel = (
            reference_emission_kernel(
                self._grid_size,
                intensity,
                self._kernel or "book_table",
                self._sigma_sq,
            )
            if self._reference_v3
            else emission_kernel(self._grid_size, intensity)
        )
        for (d_row, d_col), value in kernel.items():
            cell = (center[0] + d_row, center[1] + d_col)
            if self._in_bounds(cell):
                emitted[cell] = value
        return emitted

    def _record_before_emit(self) -> None:
        if self._transmit_lag <= 0:
            return
        self._history.append(dict(self._values))
        if len(self._history) > self._transmit_lag:
            del self._history[: -self._transmit_lag]

    def _in_bounds(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self._board_size and 0 <= cell[1] < self._board_size

    def _parse(self, key: str) -> Cell | None:
        """Turn a `"row,col"` wire key into an on-board cell, or None."""
        try:
            row_text, col_text = str(key).split(",")
            cell = (int(row_text), int(col_text))
        except ValueError:
            return None
        return cell if self._in_bounds(cell) else None
