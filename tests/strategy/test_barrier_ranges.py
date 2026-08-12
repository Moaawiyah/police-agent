"""Barrier policy across range: the distant seal, and walling against a spread belief.

Split from test_barrier.py to keep both files under the project's 150-line rule;
`police()` is the same fixture and is imported from there.
"""

from police_agent.constants import Direction
from police_agent.strategy.barrier import choose_barrier
from tests.strategy.test_barrier import police


class TestSpreadBelief:
    """A wall is weighed against the top of the distribution, not the argmax
    alone -- see tests/strategy/test_placement.py for the scoring itself."""

    def test_a_spread_belief_can_move_the_placement(self):
        state = police(start=(3, 3), board_size=7)
        alone = choose_barrier(state, (2, 4), barriers_max=5)
        spread = choose_barrier(
            state, (2, 4), barriers_max=5, belief=[((2, 4), 0.5), ((4, 4), 0.5)]
        )
        assert alone.action.direction is Direction.N  # (2, 3), first in board order
        assert spread.action.direction is Direction.E  # (3, 4), touching both cells

    def test_an_omitted_belief_puts_every_bit_of_weight_on_the_believed_cell(self):
        state = police(start=(3, 3), board_size=7)
        assert choose_barrier(state, (2, 4), barriers_max=5) == choose_barrier(
            state, (2, 4), barriers_max=5, belief=[((2, 4), 1.0)]
        )


class TestWideRangeFallsBackToThePocketBar:
    # Doorway (4, 0) is the sole connection between the open board and a
    # 14-cell room filling rows 5-6 (matches test_encirclement.py's fixture).
    _ROOM_BARRIERS = [(4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6)]

    def test_seals_a_pocket_too_far_off_to_touch_an_escape(self):
        state = police(start=(3, 0), board_size=7, barriers=self._ROOM_BARRIERS)
        decision = choose_barrier(state, believed=(3, 3), barriers_max=5)
        assert decision is not None
        assert decision.action.direction is Direction.S  # (4, 0), one step south
        assert "shrinks the pocket" in decision.rationale

    def test_still_refuses_past_wide_reach(self):
        state = police(start=(0, 0), board_size=7, barriers=self._ROOM_BARRIERS)
        assert choose_barrier(state, believed=(6, 6), barriers_max=5) is None


class TestWideRangeGainBar:
    def test_an_open_board_wide_range_wall_is_refused(self):
        """No endgame exemption exists: this exact refusal held whether it is
        round one or the match's last round -- one gain bar, every round."""
        state = police(start=(0, 0), board_size=7)
        assert choose_barrier(state, believed=(0, 3), barriers_max=5) is None
