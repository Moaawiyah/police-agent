"""Tests for the barrier policy: wall only when the wall provably corners the thief."""

import pytest

from police_agent.constants import Direction, MoveType
from police_agent.domain.own_state import OwnGameState
from police_agent.strategy.barrier import choose_barrier, direction_to
from police_agent.strategy.brain import PoliceBrain
from police_agent.strategy.threat import PointThreat, UniformThreat


def police(start, board_size=5, barriers=()):
    state = OwnGameState(start=start, board_size=board_size)
    for cell in barriers:
        state.note_barrier(cell)
    return state


class TestWhenItWalls:
    def test_walls_the_last_but_one_escape_of_a_cornered_thief(self):
        # The thief is believed in the corner (0, 0): only (0, 1) and (1, 0) remain.
        decision = choose_barrier(police(start=(1, 1)), (0, 0), barriers_max=2)
        assert decision is not None
        assert decision.action.move_type is MoveType.BARRIER
        assert decision.action.direction is Direction.N  # (0, 1), one of the two escapes

    def test_walls_the_final_escape_of_an_already_squeezed_thief(self):
        # (1, 0) is already walled, so (0, 1) is the thief's only way out of (0, 0).
        state = police(start=(1, 1), barriers=[(1, 0)])
        decision = choose_barrier(state, (0, 0), barriers_max=2)
        assert decision is not None
        assert decision.action.direction is Direction.N
        assert "0 step(s)" in decision.rationale

    def test_the_brain_prefers_the_wall_over_the_chase_step(self):
        decision = PoliceBrain().decide(police(start=(1, 1)), PointThreat((0, 0)), barriers_max=2)
        assert decision.action.move_type is MoveType.BARRIER

    def test_the_chosen_placement_is_accepted_by_the_domain_layer(self):
        state = police(start=(1, 1))
        decision = choose_barrier(state, (0, 0), barriers_max=2)
        assert state.apply_move(decision.action, barriers_max=2)
        assert (0, 1) in state.barriers
        assert state.position == (1, 1)  # walling forgoes the step (3.4)

    def test_walls_even_when_the_thief_still_has_several_escapes(self):
        # (0, 2) is two cells from the believed (2, 2) in a straight line, so
        # (1, 2) is a barrier target that is also one of its four open escapes.
        decision = choose_barrier(police(start=(0, 2)), (2, 2), barriers_max=5)
        assert decision is not None
        assert decision.action.move_type is MoveType.BARRIER


class TestWhenItRefuses:
    def test_never_walls_without_quota(self):
        assert choose_barrier(police(start=(1, 1)), (0, 0), barriers_max=0) is None

    def test_never_walls_once_the_quota_is_spent(self):
        state = police(start=(1, 1))
        state.apply_move(PoliceBrain().decide(state, PointThreat((0, 0)), 1).action, 1)
        assert state.my_barriers == 1
        assert choose_barrier(state, (0, 0), barriers_max=1) is None

    def test_never_walls_a_thief_it_cannot_reach(self):
        # (0, 0) is cornered, but three cells away no wall of ours can touch it.
        assert choose_barrier(police(start=(2, 1)), (0, 0), barriers_max=5) is None

    def test_never_walls_when_the_thief_is_already_out_of_escapes(self):
        state = police(start=(1, 1), barriers=[(0, 1), (1, 0)])
        assert choose_barrier(state, (0, 0), barriers_max=5) is None

    def test_never_walls_itself_in(self):
        """Specification 3.4: a greedy barrier "may imprison the police itself"."""
        # On a 3x3 with (1, 0) walled, the police in (0, 0) can only step east --
        # onto the very cell that would take the cornered thief's last escape.
        state = police(start=(0, 0), board_size=3, barriers=[(1, 0)])
        assert state.board.legal_moves(state.position, state.barriers) == [(Direction.E, (0, 1))]
        assert choose_barrier(state, (0, 2), barriers_max=5) is None

    def test_refusing_leaves_the_brain_free_to_chase(self):
        state = police(start=(0, 0), board_size=3, barriers=[(1, 0)])
        decision = PoliceBrain().decide(state, PointThreat((0, 2)), barriers_max=5)
        assert decision.action.move_type is MoveType.MOVE
        assert state.apply_move(decision.action, barriers_max=5)

    def test_never_walls_without_real_evidence_yet(self):
        # Same geometry as test_walls_the_last_but_one_escape_of_a_cornered_thief,
        # but nothing has been smelled: an opening diffusion artifact must not spend a wall.
        state = police(start=(1, 1))
        assert choose_barrier(state, (0, 0), barriers_max=2, has_evidence=False) is None

    def test_the_brain_chases_instead_of_walling_an_unstarted_prior(self):
        # UniformThreat.has_scent() is False by construction -- "before any scent".
        state = police(start=(1, 1))
        decision = PoliceBrain().decide(state, UniformThreat(5), barriers_max=2)
        assert decision.action.move_type is MoveType.MOVE

    def test_never_walls_the_cell_underfoot(self):
        # Standing next to the cornered thief, our own cell is its only escape --
        # and it is still refused, because walling it would deny us the cell we
        # stand on for the rest of the game.
        state = police(start=(0, 1), board_size=3, barriers=[(1, 0), (1, 1), (0, 2)])
        escapes = [target for _, target in state.board.legal_moves((0, 0), state.barriers)]
        assert escapes == [(0, 1)]
        assert choose_barrier(state, (0, 0), barriers_max=5) is None


class TestDirectionTo:
    def test_maps_each_neighbour_to_its_direction(self):
        assert direction_to((2, 2), (1, 2)) is Direction.N
        assert direction_to((2, 2), (3, 2)) is Direction.S
        assert direction_to((2, 2), (2, 3)) is Direction.E
        assert direction_to((2, 2), (2, 1)) is Direction.W

    def test_rejects_a_cell_that_is_not_one_orthogonal_step_away(self):
        """Diagonals and the cell underfoot have no direction -- catching that here
        keeps an unrepresentable placement from reaching the domain layer."""
        for cell in [(1, 1), (2, 2), (4, 2)]:
            with pytest.raises(ValueError, match="not orthogonally adjacent"):
                direction_to((2, 2), cell)


class TestDeterminism:
    def test_the_same_state_always_yields_the_same_placement(self):
        first = choose_barrier(police(start=(1, 1)), (0, 0), barriers_max=2)
        second = choose_barrier(police(start=(1, 1)), (0, 0), barriers_max=2)
        assert first == second
