"""`BeliefGrid`'s evidence-update pipeline, split out of `belief.py` to keep
the class definition under the project's line budget.

Same pattern as `belief_queries.py`: each function takes the grid as its
first argument and reaches into its private state exactly as a bound method
would -- `BeliefGrid.observe_smell` is a one-line delegate to `observe_smell`
here, so callers never see the split.
"""

from police_agent.strategy import belief_queries as queries


def observe_smell(grid, cells: dict | None) -> None:
    """`1 + trust*reading**power` per smelly cell, where `reading` is that
    cell's intensity relative to THIS snapshot's own peak, not an absolute
    value -- a broadly faded field (lag, distance, time since deposit) still
    has a relatively freshest cell, and evidence should concentrate there,
    since an absolute reading would starve it for being dim overall. Then
    normalise and leak toward uniform. No reading rules a cell out -- silence
    is not evidence of absence. Malformed entries are skipped, not fatal."""
    parsed: dict = {}
    for key, value in (cells or {}).items():
        cell = grid._parse(key)
        if cell is not None and isinstance(value, int | float):
            parsed[cell] = min(1.0, max(0.0, float(value)))  # negative here can turn complex
    peak = max(parsed.values(), default=0.0)
    supported: set = set()
    if peak > 0.0:
        for cell, intensity in parsed.items():
            reading = intensity / peak
            boost = 1.0 + grid._smell_trust * reading**grid._smell_power
            grid._probs[cell[0]][cell[1]] *= boost
            grid._observed = True
            if reading >= grid._stale_support:
                supported.add(cell)
    _shrink_unsupported(grid, supported)
    grid._normalize()
    queries.leak_toward_uniform(grid)


def _shrink_unsupported(grid, supported: set) -> None:
    """Every cell this reading didn't clear the support bar for loses a
    further stale_decay share of its mass -- silent, faint, or never
    touched alike. A cell unsupported N turns running gets this N times in
    a row, so the shrink compounds on its own; normalize() right after is
    what redistributes the freed mass, the same way it already absorbs the
    boost loop's non-conservation above."""
    if grid._stale_decay >= 1.0:
        return
    for row in range(grid._size):
        for col in range(grid._size):
            if (row, col) not in supported:
                grid._probs[row][col] *= grid._stale_decay
