"""Medium-range barrier placement: seal a pocket before the police is adjacent.

`barrier.py`'s escape-overlap check is a hard geometric bound -- it can only
ever fire within its own `BARRIER_REACH` (2), because that is the farthest a
candidate cell can simultaneously reach both the police and the believed
thief cell (triangle inequality; see that module's docstring). Past that
distance a wall can still be worth placing, but "worth it" has to be judged
differently: not by whether it removes one of the thief's immediate escapes
-- geometrically impossible to check from here -- but by how much it shrinks
the thief's whole reachable pocket.

One lesson is borrowed from the course reference and deliberately not
repeated: its equivalent widens engagement to distance 4 with a flat
`min_gain=1`, which accepts nearly any nearby wall. Measured against an
actively fleeing thief, that policy never converted a single one of 39 test
starts within the move ceiling -- every barrier turn is a STAY, and a STAY
against a thief that is fleeing is a full step of ground given back for free.
So `MIN_GAIN_FRACTION` sets a much higher bar: a wide placement only
qualifies when it removes a real fraction of the pocket, not just one cell
of it, and it must never raise the police's own barrier-aware distance to
the target.
"""

from police_agent.constants import Cell
from police_agent.domain.board import Board

WIDE_REACH = 4

# A wide-range wall must remove at least this fraction of the thief's
# reachable pocket to be worth a full turn's tempo.
MIN_GAIN_FRACTION = 0.34
# ...and never for a shrink smaller than this many cells outright, so the
# fraction cannot be satisfied by a trivially small pocket.
MIN_GAIN_FLOOR = 2

# Once this few rounds remain, an unused barrier scores nothing anyway, so
# the tempo cost that makes a marginal wall a bad trade earlier in the match
# no longer applies the same way -- there is no future chase left to protect.
# A deliberate, measured tradeoff, not a free improvement: loosening only
# inside this window raises mean barrier usage roughly 3-4x (0.51 -> ~1.9 per
# match against the adversarial benchmark) at a real, accepted cost to
# capture rate (~86% -> ~72%). `wide_placement` is only ever this permissive
# when a caller explicitly passes `rounds_left`; omitting it keeps the
# ordinary, tempo-protective threshold.
ENDGAME_ROUNDS = 10
ENDGAME_MIN_GAIN_FLOOR = 1
ENDGAME_MIN_GAIN_FRACTION = 0.0


def wide_placement(
    board: Board,
    position: Cell,
    barriers: set[Cell],
    believed: Cell,
    rounds_left: int | None = None,
) -> Cell | None:
    """The best distant wall worth its tempo against `believed`, or None.

    Every candidate is tried and the largest qualifying gain wins, rather than
    the first one found -- unlike the close-range check, there is no "first
    valid" reading of the rules to stay faithful to here, so ranking by actual
    effect is the more defensible tie-break.
    """
    endgame = rounds_left is not None and rounds_left <= ENDGAME_ROUNDS
    min_floor = ENDGAME_MIN_GAIN_FLOOR if endgame else MIN_GAIN_FLOOR
    min_fraction = ENDGAME_MIN_GAIN_FRACTION if endgame else MIN_GAIN_FRACTION

    before_area = board.reachable_area(believed, barriers)
    before_gap = board.shortest_path_length(position, believed, barriers)
    if before_gap is None:
        return None
    threshold = max(min_floor, int(before_area * min_fraction))

    best: tuple[int, Cell] | None = None
    for cell in board.barrier_targets(position, barriers):
        if cell in (position, believed):
            continue
        trial = barriers | {cell}
        if not board.legal_moves(position, trial):
            continue  # would confine the police itself (3.4)
        after_gap = board.shortest_path_length(position, believed, trial)
        if after_gap is None or after_gap > before_gap:
            continue  # never trade away our own ground to seal a pocket
        gain = before_area - board.reachable_area(believed, trial)
        if gain < threshold:
            continue
        if best is None or gain > best[0]:
            best = (gain, cell)
    return best[1] if best else None
