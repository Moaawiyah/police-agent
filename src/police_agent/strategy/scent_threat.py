"""A threat estimate read straight off the opponent's scent trail.

This is the *interim* estimate, and it is worth being clear about what it is
not. It takes the strongest cell in the most recent scent grid and calls that
the thief's location. It keeps no prior, does not diffuse between turns, and
throws away everything it learned last turn. A real Dec-POMDP belief does all
three, and that is the Bayesian belief map of build step 6.

It exists because the runtime needs *some* `ThreatEstimate` to chase, and a
placeholder that reads the real signal is far more honest than one that returns
a fixed cell: it makes the turn loop genuinely dependent on what the opponent
sends, so the wiring is exercised end to end. When `BeliefGrid` lands it
satisfies the same protocol and replaces this class at the runtime's one
construction site.
"""

from police_agent.constants import Cell


class ScentThreat:
    """Argmax of the last received scent grid, falling back to the board centre."""

    def __init__(self, board_size: int) -> None:
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        self.board_size = board_size
        self._cells: dict[Cell, float] = {}

    def absorb(self, smell_grid: dict) -> None:
        """Take in one scent grid, `{"r,c": intensity}`, replacing the last.

        Malformed keys are skipped rather than raised on. The grid comes from
        another team's implementation, and a single unparseable entry is not a
        reason to abandon a game that is otherwise proceeding correctly -- the
        remaining cells still carry the signal.
        """
        parsed: dict[Cell, float] = {}
        for key, value in (smell_grid or {}).items():
            cell = self._parse(key)
            if cell is not None and isinstance(value, (int, float)):
                parsed[cell] = float(value)
        if parsed:
            self._cells = parsed

    def most_likely(self) -> Cell:
        """The strongest-smelling cell; the centre when nothing has arrived yet.

        Ties break on the cell order, so the same grid always yields the same
        answer -- the strategy above this is deterministic and would lose that
        property if its input were not.
        """
        if not self._cells:
            middle = (self.board_size - 1) // 2
            return (middle, middle)
        return max(sorted(self._cells), key=lambda cell: self._cells[cell])

    def _parse(self, key: str) -> Cell | None:
        """Turn a `"row,col"` wire key into an on-board cell, or None."""
        try:
            row_text, col_text = str(key).split(",")
            cell = (int(row_text), int(col_text))
        except ValueError:
            return None
        if 0 <= cell[0] < self.board_size and 0 <= cell[1] < self.board_size:
            return cell
        return None
