"""Pure board geometry for an N x N grid.

The Board is stateless with respect to the game: it stores no positions and no
barriers, and only answers geometric questions. Each peer owns its own mutable
state elsewhere (see own_state.py) and passes the known barrier set in per call,
which keeps the geometry trivially testable and free of hidden shared state.
"""

from police_agent.constants import DELTAS, Cell, Direction


class Board:
    """An N x N grid with single-step orthogonal movement."""

    def __init__(self, size: int) -> None:
        if size < 1:
            raise ValueError(f"Board size must be positive, got {size}")
        self.size = size

    def in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    def distance(self, a: Cell, b: Cell) -> int:
        """Manhattan distance: the true move-distance when diagonals are illegal."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def step(
        self, origin: Cell, direction: Direction, barriers: set[Cell] | None = None
    ) -> Cell | None:
        """The cell reached from `origin`, or None if it is off-board or walled."""
        d_row, d_col = DELTAS[direction]
        target = (origin[0] + d_row, origin[1] + d_col)
        if not self.in_bounds(target):
            return None
        if barriers and target in barriers:
            return None
        return target

    def neighbors(self, cell: Cell, barriers: set[Cell] | None = None) -> list[Cell]:
        """Every reachable orthogonally adjacent cell."""
        return [t for d in Direction if (t := self.step(cell, d, barriers)) is not None]

    def legal_moves(
        self, origin: Cell, barriers: set[Cell] | None = None
    ) -> list[tuple[Direction, Cell]]:
        """(direction, target) for every legal single step from `origin`."""
        return [(d, t) for d in Direction if (t := self.step(origin, d, barriers)) is not None]

    def barrier_targets(self, origin: Cell, barriers: set[Cell] | None = None) -> list[Cell]:
        """The cells the police may wall while standing on `origin`.

        Specification 3.4: "the cell it stands on itself, or one of the four
        orthogonally adjacent cells" -- five candidates, not four. Including the
        origin is what allows the police to wall the thief's cell after stepping
        onto it. Cells that are off-board or already walled are excluded.
        """
        walled = barriers or set()
        here = [origin] if self.in_bounds(origin) and origin not in walled else []
        return here + self.neighbors(origin, barriers)

    def reachable_area(
        self, start: Cell, barriers: set[Cell] | None = None, limit: int | None = None
    ) -> int:
        """How many cells `start` can still reach -- a flood fill, not a distance.

        `distance` is Manhattan and blind to barriers; this is what a barrier
        placement actually shrinks. `limit` stops the fill early once it no
        longer matters (`strategy/encirclement.py` only cares whether an area is
        "small" or "large", not its exact size once it is clearly large).
        """
        seen = {start}
        frontier = [start]
        while frontier and (limit is None or len(seen) < limit):
            nxt = []
            for cell in frontier:
                for neighbor in self.neighbors(cell, barriers):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        nxt.append(neighbor)
            frontier = nxt
        return len(seen)

    def shortest_path_length(
        self, start: Cell, goal: Cell, barriers: set[Cell] | None = None
    ) -> int | None:
        """BFS distance honouring `barriers`, or None if `goal` is unreachable.

        `distance` (Manhattan) is a lower bound only; once barriers exist the
        true remaining chase can be longer, or the target can be cut off
        entirely -- something a barrier's own evaluation must be able to see.
        """
        if start == goal:
            return 0
        seen = {start}
        frontier = [start]
        steps = 0
        while frontier:
            steps += 1
            nxt = []
            for cell in frontier:
                for neighbor in self.neighbors(cell, barriers):
                    if neighbor == goal:
                        return steps
                    if neighbor not in seen:
                        seen.add(neighbor)
                        nxt.append(neighbor)
            frontier = nxt
        return None
