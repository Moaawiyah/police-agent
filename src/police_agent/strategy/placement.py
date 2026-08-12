"""Which cell to wall: score every candidate, keep the best one.

The police has at most five legal placements on any turn -- the cell underfoot
and its four neighbours (3.4) -- so there is no reason to accept the first one
that happens to help. Every candidate is scored and the best wins.

A candidate is worth two separate things, and the score is their sum:

* an *immediate escape* removed, when the wall lands on a cell the thief could
  have stepped to next turn;
* *reachable area* removed, the pocket the thief is left with after the wall,
  which is what a wall far from the thief can still take away.

Only the second term can fire past two cells: a wall one step from the police
and one step from the thief needs both to be within two of each other
(triangle inequality), so beyond that the escape term is zero by geometry, not
by policy. That is why one scorer covers both the close chase and the distant
seal -- the range split that used to exist was the geometry, not a decision.

Both terms are measured across the top-K belief cells rather than the argmax
alone, weighted by probability. The argmax is a point estimate of a
distribution that is rarely peaked, and a wall spent as if the top cell were
certain ignores the mass sitting one cell over.

The safety rules are not part of the score. They are absolute: a candidate that
breaks one is not ranked lower, it is not a candidate. Scoring is exact
arithmetic over a fixed candidate order, so a placement stays recomputable from
replayed state in the end-of-game audit.
"""

from police_agent.constants import Cell
from police_agent.domain.board import Board
from police_agent.strategy.encirclement import pocket_bar

# How many belief cells a placement is weighed against. Measured on a 360-start
# benchmark against a thief that flees once it sees the police, capture rate
# peaks sharply here: 0.6% at K=1, 1.4% at K=2, 2.8% at K=3, then back down
# (1.9% at K=4, 0.6% at K=8) as the tail of the distribution drowns the head.
TOP_K = 3

# What one removed escape is worth in cells of pocket. A tie-break between the
# two score terms, not a rule: it only decides which legal wall is spent, never
# whether walling is allowed.
#
# Deliberately below one, which is not the intuitive setting. Weighting an
# escape heavily (4, 8, 16 -- all identical) walls whichever cell the thief
# could step to next and ignores what that wall does to the rest of its ground;
# on the same benchmark that scores 1.7% against 2.8% here, and 0.3% at 64.
# Removing an escape already gets the wall past the acceptance bar in
# `best_placement`; it does not also need to dominate the ranking.
ESCAPE_WEIGHT = 0.5


def best_placement(
    board: Board,
    position: Cell,
    barriers: set[Cell],
    believed: Cell,
    belief: list[tuple[Cell, float]],
) -> tuple[Cell, bool] | None:
    """The highest-scoring legal wall, and whether it takes an immediate escape.

    `believed` is the primary target: it alone decides the safety rules and the
    acceptance bar, so what the audit has to re-derive is unchanged by the
    top-K weighting, which only ranks the candidates that already qualify.

    None when nothing qualifies -- including when the thief is already beyond
    the police's own reach, since a wall cannot help a chase that has no path
    to begin with and may only seal the target somewhere unreachable.
    """
    before_gap = board.shortest_path_length(position, believed, barriers)
    if before_gap is None:
        return None
    escapes = {target for _, target in board.legal_moves(believed, barriers)}
    bar = pocket_bar(board, believed, barriers)
    weights = _normalised(belief, believed)

    best: tuple[float, Cell, bool] | None = None
    for cell in board.barrier_targets(position, barriers):
        if cell in (position, believed):
            continue  # never the cell underfoot, never the believed cell itself
        trial = barriers | {cell}
        if not board.legal_moves(position, trial):
            continue  # would imprison the police behind its own wall (3.4)
        takes_escape = cell in escapes
        if not (takes_escape and len(escapes) == 1):
            # Sealing the thief's last escape *is* the capture, so it alone may
            # cost us ground. Anything else must not lengthen our own path.
            after_gap = board.shortest_path_length(position, believed, trial)
            if after_gap is None or after_gap > before_gap:
                continue
        if not takes_escape and _area_gain(board, barriers, believed, cell) < bar:
            continue  # too small a shrink to be worth forgoing the step
        score = _score(board, barriers, weights, cell)
        if best is None or score > best[0]:
            best = (score, cell, takes_escape)
    return (best[1], best[2]) if best else None


def _score(
    board: Board, barriers: set[Cell], weights: list[tuple[Cell, float]], cell: Cell
) -> float:
    """Expected escape removal plus expected area removal, over the belief."""
    total = 0.0
    for target, weight in weights:
        if target == cell:
            continue  # a walled cell is not somewhere the thief can be standing
        escape = 1.0 if board.distance(target, cell) == 1 else 0.0
        area = _area_gain(board, barriers, target, cell)
        total += weight * (ESCAPE_WEIGHT * escape + area)
    return total


def _area_gain(board: Board, barriers: set[Cell], target: Cell, cell: Cell) -> int:
    """How many cells walling `cell` takes away from `target`'s pocket."""
    return board.reachable_area(target, barriers) - board.reachable_area(target, barriers | {cell})


def _normalised(belief: list[tuple[Cell, float]], believed: Cell) -> list[tuple[Cell, float]]:
    """Belief weights summing to one, or all the weight on `believed`.

    A top-K slice of a distribution does not sum to one, and the score has to
    stay comparable against the acceptance bar, which is measured in cells.
    """
    total = sum(weight for _, weight in belief if weight > 0.0)
    if total <= 0.0:
        return [(believed, 1.0)]
    return [(cell, weight / total) for cell, weight in belief if weight > 0.0]
