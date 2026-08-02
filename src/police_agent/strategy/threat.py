"""ThreatEstimate: everything the strategy is allowed to know about the thief.

The police never learns the thief's true cell while the game is running (see
domain/rules.py): it only ever holds a *belief* reconstructed from scent. So the
strategy must not take a thief position as an argument -- it takes an estimate.

This module deliberately states the narrowest possible interface: the single
question a chase heuristic actually asks. Keeping it that narrow is what lets
strategy be built before the Bayesian belief map exists. The `BeliefGrid` of the
scent/belief step will satisfy `ThreatEstimate` structurally the moment it is
written, because it already answers `most_likely()` -- nothing in this package
will need to change then, and nothing here depends on that step landing first.

The two concrete estimates below exist so the strategy is testable and the local
simulation is runnable in the meantime.
"""

from typing import Protocol, runtime_checkable

from police_agent.constants import Cell


@runtime_checkable
class ThreatEstimate(Protocol):
    """The one question the police strategy asks about the thief's location.

    Structural, not inherited: an implementation only has to answer the method,
    it must not import or subclass anything from this package.
    """

    def most_likely(self) -> Cell:
        """The cell the thief is currently believed most likely to occupy."""
        ...


class PointThreat:
    """A belief collapsed onto one cell -- "the thief is right there".

    This is the estimate a test or a scripted local simulation supplies when it
    wants a known, fixed target. It is never how the real agent learns a
    position: a point belief is what a *perfect* observation would produce, and
    the police never gets one during play.
    """

    def __init__(self, cell: Cell) -> None:
        self.cell = cell

    def most_likely(self) -> Cell:
        return self.cell


class UniformThreat:
    """The flat prior the police holds before any scent has been received.

    Every cell is equally likely, so the argmax is arbitrary and any tie-break
    would do. The board centre is chosen because it is the answer that still
    steers the police somewhere useful: it minimises the worst-case distance to
    whichever cell the thief actually turns out to occupy.
    """

    def __init__(self, board_size: int) -> None:
        if board_size < 1:
            raise ValueError(f"Board size must be positive, got {board_size}")
        self.board_size = board_size

    def most_likely(self) -> Cell:
        middle = (self.board_size - 1) // 2
        return (middle, middle)
