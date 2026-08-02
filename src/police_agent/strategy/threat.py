"""ThreatEstimate: everything the strategy is allowed to know about the thief.

The police never learns the thief's true cell while the game is running (see
domain/rules.py): it only ever holds a *belief* reconstructed from scent. So the
strategy must not take a thief position as an argument -- it takes an estimate.

The interface is deliberately the narrowest one the turn loop actually uses:
two calls to fold in what a turn revealed, and one question the chase heuristic
asks. `strategy/belief.py::BeliefGrid` is the real implementation; the two
concrete estimates below exist so the strategy stays testable against a known,
fixed target and so a scripted simulation can be run without a live opponent.

The stand-ins do not diffuse and do not observe. That is not an oversight: a
certainty has nothing to spread and nothing to learn, and giving them real
behaviour would make them a second, quietly diverging belief map.
"""

from typing import Protocol, runtime_checkable

from police_agent.constants import Cell


@runtime_checkable
class ThreatEstimate(Protocol):
    """What the turn loop tells an estimate, and the one thing it asks back.

    Structural, not inherited: an implementation only has to answer the methods,
    it must not import or subclass anything from this package.
    """

    def diffuse(self) -> None:
        """The thief has moved. Spread the belief over where it could now be."""
        ...

    def observe_smell(self, cells: dict | None) -> None:
        """Fold in one received scent grid, `{"r,c": intensity}`."""
        ...

    def scale(self, cells, factor: float) -> None:
        """Reweight a set of cells -- evidence that did not arrive as scent."""
        ...

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

    def diffuse(self) -> None:
        """A fixed target does not drift; the point of it is that it holds still."""

    def observe_smell(self, cells: dict | None) -> None:
        """Certainty has nothing to learn from a scent reading."""

    def scale(self, cells, factor: float) -> None:
        """Nor from a hint. A fixed target is fixed against all evidence."""

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

    def diffuse(self) -> None:
        """A flat prior is already maximally spread; diffusing it changes nothing."""

    def observe_smell(self, cells: dict | None) -> None:
        """Staying uniform is what makes this the *prior* rather than a belief."""

    def scale(self, cells, factor: float) -> None:
        """A prior that reweighted itself on evidence would be a belief map."""

    def most_likely(self) -> Cell:
        middle = (self.board_size - 1) // 2
        return (middle, middle)
