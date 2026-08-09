"""The shape of a single emission: how strongly each cell near an agent smells.

Split from `scent.py` because it answers a different question. This module knows
what one deposit looks like -- a fixed picture, the same every time. `scent.py`
knows what happens to deposits over a game, as they overlap and fade. Only this
half is what the two teams must agree on curve-for-curve (ch. 4.5).

The book gives the falloff only as a picture: figure 4's 5x5 window reading
0.90 / 0.62 / 0.42 / 0.20 / 0.14 / 0.04 outwards from the centre. A Gaussian
over Euclidean distance at the sigma below reproduces all six values to the
printed precision, which is as close as a formula can be pinned to a figure.

That makes sigma a *choice*, not a constant handed down: ch. 4.5 explicitly
leaves the curve to the two groups to agree and hash. It is not a signed term
and must not become one -- `peer/terms.py` is frozen against the reference's key
set, and adding to it would fail every handshake.
"""

import math

# Reference-v3's ``book_table`` is a literal lookup, not a Gaussian estimate.
# Keeping the values here avoids the small diagonal drift that the old Police
# kernel introduced when it rounded a formula instead of using Figure 4.
BOOK_FIGURE_KERNEL: tuple[tuple[float, ...], ...] = (
    (0.04, 0.14, 0.20, 0.14, 0.04),
    (0.14, 0.42, 0.62, 0.42, 0.14),
    (0.20, 0.62, 0.90, 0.62, 0.20),
    (0.14, 0.42, 0.62, 0.42, 0.14),
    (0.04, 0.14, 0.20, 0.14, 0.04),
)

REFERENCE_GAUSSIAN_SIGMA_SQ = 4.0 / 3.0

# Distances are measured in cells, so the useful ones are the small integers:
# 0, 1, sqrt(2), 2, sqrt(5), 2*sqrt(2) inside a 5x5 window.
_FALLOFF_SIGMA = 1.15


def emission_kernel(grid_size: int, intensity: float) -> dict[tuple[int, int], float]:
    """One deposit as offsets from its centre, `(d_row, d_col) -> intensity`.

    Offsets rather than cells because the shape is the same wherever it lands;
    the caller translates it and clips it to the board. Nothing is emitted
    outside the agreed window, which is what keeps a trail local.
    """
    half = grid_size // 2
    spread = 2.0 * _FALLOFF_SIGMA**2
    return {
        (d_row, d_col): round(intensity * math.exp(-(d_row**2 + d_col**2) / spread), 3)
        for d_row in range(-half, half + 1)
        for d_col in range(-half, half + 1)
    }


def reference_emission_kernel(
    grid_size: int,
    intensity: float,
    mode: str = "book_table",
    sigma_sq: float = REFERENCE_GAUSSIAN_SIGMA_SQ,
) -> dict[tuple[int, int], float]:
    """Return the reference-v3 emission table as offset/value pairs.

    The shipped reference uses the printed 5x5 table for its default
    ``book_table`` mode. Non-default dimensions/intensities fall back to the
    reference's closed-form Gaussian option, which keeps this adapter useful
    for peers that negotiate the optional variant explicitly.
    """
    if mode == "book_table" and grid_size == 5 and abs(float(intensity) - 0.9) <= 1e-9:
        table = BOOK_FIGURE_KERNEL
        half = 2
        return {
            (row - half, col - half): value
            for row, values in enumerate(table)
            for col, value in enumerate(values)
        }
    if mode not in {"book_table", "gaussian"}:
        raise ValueError(f"unknown pheromone_kernel {mode!r}")
    half = grid_size // 2
    spread = 2.0 * float(sigma_sq)
    return {
        (d_row, d_col): round(float(intensity) * math.exp(-(d_row**2 + d_col**2) / spread), 2)
        for d_row in range(-half, half + 1)
        for d_col in range(-half, half + 1)
    }
