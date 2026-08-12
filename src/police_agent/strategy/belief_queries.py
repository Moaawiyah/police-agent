"""`BeliefGrid`'s read-side queries, split out of `belief.py` to keep the
update pipeline (`__init__`, `diffuse`, `observe_smell`) under the project's
line budget.

Each function takes the grid as its first argument and reaches into its
private state (`grid._probs`, `grid._in_bounds`, `grid._normalize`) exactly as
a bound method would -- `BeliefGrid`'s own methods are one-line delegates to
these, so callers never see the split. Same pattern `infra/mcp_client_ops.py`
uses for `McpTransport`.
"""

from police_agent.constants import Cell


def scale(grid, cells, factor: float) -> None:
    """Reweight cells for non-scent evidence, then renormalise -- caller's judgement."""
    for cell in cells:
        if grid._in_bounds(cell):
            grid._probs[cell[0]][cell[1]] *= factor
    grid._normalize()


def exclude(grid, cell: Cell) -> None:
    """Rule a cell out entirely -- something proved the thief is not standing there."""
    if grid._in_bounds(cell):
        grid._probs[cell[0]][cell[1]] = 0.0
        grid._normalize()


def most_likely(grid) -> Cell:
    """The argmax; ties break row-major so the same evidence always answers the same."""
    return top_cells(grid, 1)[0][0]


def top_cells(grid, count: int = 1) -> list[tuple[Cell, float]]:
    """The `count` likeliest cells and their probabilities, likeliest first.

    The argmax alone is a point estimate of a distribution that is rarely
    peaked, so the barrier policy weighs a wall against several cells.
    Ordering by `(-prob, cell)` keeps the row-major tie-break `most_likely`
    has always had, so this stays recomputable in the end-of-game audit."""
    cells = ((row, col) for row in range(grid._size) for col in range(grid._size))
    ranked = sorted(cells, key=lambda c: (-grid._probs[c[0]][c[1]], c))
    return [(cell, grid._probs[cell[0]][cell[1]]) for cell in ranked[:count]]


def as_matrix(grid) -> list[list[float]]:
    """A copy of the distribution, for the heatmap and the game log."""
    return [row[:] for row in grid._probs]


def has_scent(grid) -> bool:
    """Whether any real scent evidence has been observed yet."""
    return grid._observed


def leak_toward_uniform(grid) -> None:
    """Only observe_smell leaks -- others already normalise; twice would double it."""
    if grid._leak <= 0.0:
        return
    uniform = 1.0 / (grid._size * grid._size)
    grid._probs = [
        [(1.0 - grid._leak) * prob + grid._leak * uniform for prob in row] for row in grid._probs
    ]
