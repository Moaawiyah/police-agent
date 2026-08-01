"""Action: one turn's chosen move, validated on construction.

Bundling the move type with its direction keeps the shape rules in one place
instead of re-checking them in every caller. The rules differ per action:

* MOVE always needs a direction.
* BARRIER takes an *optional* direction -- omitting it means "wall the cell I
  stand on", the fifth placement the specification allows (3.4).
* HOLD must not carry a direction at all.
"""

from dataclasses import dataclass

from police_agent.constants import Direction, MoveType


@dataclass(frozen=True)
class Action:
    """A peer's action for one turn. Frozen so a logged action cannot be edited."""

    move_type: MoveType
    direction: Direction | None = None

    def __post_init__(self) -> None:
        if self.move_type is MoveType.MOVE and self.direction is None:
            raise ValueError("MOVE requires a direction")
        if self.move_type is MoveType.HOLD and self.direction is not None:
            raise ValueError("HOLD must not carry a direction")

    def __str__(self) -> str:
        return f"{self.move_type.value}:{self.direction.value if self.direction else '-'}"


def move(direction: Direction) -> Action:
    """Step one cell in `direction`."""
    return Action(MoveType.MOVE, direction)


def barrier(direction: Direction | None = None) -> Action:
    """Wall an adjacent cell, or the cell underfoot when `direction` is omitted."""
    return Action(MoveType.BARRIER, direction)


def hold() -> Action:
    """Stay put for this turn."""
    return Action(MoveType.HOLD)
