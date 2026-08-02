"""Compass geometry over the board, and finding the freshest cell of a trail.

Split from `strategy/bluff.py` so that module can be about judgement alone. Every
question here has an answer that does not depend on whom you believe: which
cells lie north of this one, where a scent grid is strongest, whether a bearing
and a smell point the same way.
"""

from police_agent.constants import Cell, Direction


def strongest_cell(smell_grid) -> Cell | None:
    """The freshest cell of a received `{"r,c": intensity}` trail, or None.

    Unparseable keys are skipped, as everywhere else a grid written by another
    team's implementation is read. Ties break on cell order, so two peers looking
    at the same trail reach the same conclusion about it.
    """
    best, best_value = None, 0.0
    for key, value in sorted((smell_grid or {}).items()):
        if not isinstance(value, int | float) or float(value) <= best_value:
            continue
        try:
            row, col = (int(part) for part in str(key).split(","))
        except ValueError:
            continue
        best, best_value = (row, col), float(value)
    return best


def cells_toward(origin: Cell, direction: Direction, size: int) -> list[Cell]:
    """Every cell strictly on one side of `origin`.

    A half-plane rather than a line: a bearing is not an address, and the thief
    could be anywhere along it.
    """
    rows, cols = range(size), range(size)
    if direction is Direction.N:
        return [(row, col) for row in rows if row < origin[0] for col in cols]
    if direction is Direction.S:
        return [(row, col) for row in rows if row > origin[0] for col in cols]
    if direction is Direction.W:
        return [(row, col) for row in rows for col in cols if col < origin[1]]
    return [(row, col) for row in rows for col in cols if col > origin[1]]


def agrees(direction: Direction, origin: Cell, target: Cell) -> bool | None:
    """Does `target` lie the way `direction` points from `origin`? None if neither.

    Judged one axis at a time, so a north claim against a north-east trail still
    agrees: it was said to be north and it is north, whatever else is also true
    of it. Only the exact opposite disagrees, and a bearing about the axis the
    two cells share proves nothing either way.
    """
    offset = {
        Direction.N: origin[0] - target[0],
        Direction.S: target[0] - origin[0],
        Direction.W: origin[1] - target[1],
        Direction.E: target[1] - origin[1],
    }[direction]
    return None if offset == 0 else offset > 0
