"""How large a pocket shrink is worth spending a turn on.

Placing a barrier forgoes the step (3.4), so a wall that achieves nothing is a
STAY, and a STAY against a thief that is fleeing hands back a full step of
ground for free. This module owns the one number that decides when a shrink is
worth that: the bar a placement must clear when it is *not* taking an immediate
escape away.

Two lessons are recorded here rather than rediscovered later.

The course reference widens engagement to distance 4 with a flat `min_gain=1`,
which accepts nearly any nearby wall. Measured against an actively fleeing
thief that sees the police exactly, that policy converted none of 360 test
starts within the move ceiling -- neither does ours, on an open board, because
a perfect fleer simply cannot be caught in the open. So capture rate is the
wrong instrument at this bar, and the tuning below is measured on how small a
pocket the police leaves the thief instead.

The bar also does not loosen near the end of a match. An endgame exemption once
raised it on the reasoning that an unused barrier scores nothing at game end,
but that traded real, measured confinement for barrier usage that only looked
better on paper. One bar, every round.

`strategy/placement.py` is the only caller; it applies this to candidates that
remove no immediate escape, at every range.
"""

from police_agent.constants import Cell
from police_agent.domain.board import Board

# The outer engagement range. Past this the police is simply too far away for a
# wall of its to bear on the thief at all, and the turn is better spent closing.
WIDE_REACH = 4

# A wall that removes no immediate escape must remove at least this fraction of
# the thief's reachable pocket...
MIN_GAIN_FRACTION = 0.22
# ...and never for a shrink smaller than this many cells outright, so the
# fraction cannot be satisfied by a trivially small pocket.
MIN_GAIN_FLOOR = 2

# Of the two, the floor is the one that does the work, and that is worth being
# explicit about because it is not what the fraction's name suggests. Swept from
# 0.10 to 0.50 on a 360-start benchmark, MIN_GAIN_FRACTION changed nothing at
# all: walling one cell of open board disconnects nothing and gains exactly 1,
# which is under the floor at every setting, while sealing a room's doorway
# gains a dozen or more, which clears every setting. The gains are bimodal, so
# the fraction almost never lands between them. It is kept as the guard for the
# case the floor cannot cover -- a pocket small enough that losing two cells of
# it is not worth a turn -- and 0.22 is simply a value low enough not to refuse
# real seals on a full board.


def pocket_bar(board: Board, believed: Cell, barriers: set[Cell]) -> int:
    """The smallest area reduction worth a turn against a thief at `believed`."""
    area = board.reachable_area(believed, barriers)
    return max(MIN_GAIN_FLOOR, int(area * MIN_GAIN_FRACTION))
