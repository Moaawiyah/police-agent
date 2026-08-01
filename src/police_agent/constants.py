"""Immutable game vocabulary: roles, action types and the legal directions.

These are physics, not configuration. The specification (Appendix Vav, table 15)
marks the move set as *fixed*: a single orthogonal step or staying put, with
diagonal movement forbidden. Modelling only N/S/E/W here means an illegal
diagonal cannot be represented at all, rather than merely being rejected later.
"""

from enum import StrEnum

# (row, column). The row index grows downward/south, matching the coordinate
# system agreed in config/*/game.json ("axis_origin_corner": "top-left").
Cell = tuple[int, int]


class Role(StrEnum):
    """Which side a peer plays. Roles alternate across a series of sub-games."""

    POLICE = "police"
    THIEF = "thief"


class MoveType(StrEnum):
    """The actions a peer may take on its turn."""

    MOVE = "MOVE"  # step one cell orthogonally
    BARRIER = "BARRIER"  # police only: forgo the step and wall a cell instead
    HOLD = "HOLD"  # stay put


class Direction(StrEnum):
    """The four orthogonal directions. Diagonals are illegal by specification."""

    N = "N"
    S = "S"
    E = "E"
    W = "W"


DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.N: (-1, 0),
    Direction.S: (1, 0),
    Direction.E: (0, 1),
    Direction.W: (0, -1),
}
