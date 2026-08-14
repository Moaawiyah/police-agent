"""`ScentField`'s merge/decay/wire-format operations, split out of scent.py
to keep that file under the project's line budget.

Same convention as `strategy/belief_queries.py`: each function takes the
field as its first argument and reaches into its private state exactly as a
bound method would -- `ScentField`'s own methods are one-line delegates to
these, so callers never see the split.
"""

from police_agent.constants import Cell

# Intensities cross the wire rounded to three decimals so both peers hold them
# identically. That rounding has a floor: multiply anything at or under 0.005 by
# 0.9 and it rounds back to itself, staining the board forever. Dropping below a
# hundredth clears the sticky region and still outlasts the agreed 35-move
# ceiling -- a full-strength trail only gets there after some forty turns.
TRACE_FLOOR = 0.01


def absorb(field, cells: dict | None) -> None:
    """Merge a received `{"r,c": intensity}` grid into this field, max wins.

    Malformed entries are skipped, not raised on: the grid comes from
    another team's implementation, and forfeiting a match over one
    unparseable key would throw away a game still perfectly playable.
    Values are clamped to `[0, 1]` too -- a stray negative or oversized number
    should not be able to poison this peer's own view."""
    for key, value in (cells or {}).items():
        cell = field._parse(key)
        if cell is not None and isinstance(value, int | float):
            intensity = min(1.0, max(0.0, float(value)))
            field._values[cell] = max(field._values.get(cell, 0.0), intensity)


def decay_all(field) -> None:
    """One full turn of fading: every trail keeps `1 - rho` of its strength.

    A cell loses a tenth of what it has, so it thins fast while strong and
    lingers once faint -- the historical shoulder the chapter asks for. Worn
    past the trace floor it is dropped rather than left as a stain.
    """
    for cell in list(field._values):
        faded = round(field._values[cell] * (1.0 - field._decay), 3)
        if faded >= TRACE_FLOOR:
            field._values[cell] = faded
        else:
            del field._values[cell]


def snapshot(field) -> dict[str, float]:
    """The wire form: `{"r,c": intensity}` for every cell that still smells."""
    return {f"{row},{col}": value for (row, col), value in field._values.items() if value > 0.0}


def parse(field, key: str) -> Cell | None:
    """Turn a `"row,col"` wire key into an on-board cell, or None."""
    try:
        row_text, col_text = str(key).split(",")
        cell = (int(row_text), int(col_text))
    except ValueError:
        return None
    return cell if field._in_bounds(cell) else None
