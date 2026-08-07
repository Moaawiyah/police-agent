"""Tests for the police move policy: chase, tie-breaks, and the never-illegal contract."""

import random

import pytest

from police_agent.constants import Direction, MoveType
from police_agent.domain.own_state import OwnGameState
from police_agent.strategy.brain import PoliceBrain, PoliceBrainBase
from police_agent.strategy.decision import Decision
from police_agent.strategy.threat import PointThreat


def police(start=(2, 2), board_size=5):
    return OwnGameState(start=start, board_size=board_size)


def wall_in(state):
    """Wall every neighbour so the police has no legal step left."""
    for cell in state.board.neighbors(state.position):
        state.note_barrier(cell)


class TestChase:
    def test_steps_toward_the_believed_cell(self):
        decision = PoliceBrain().decide(police(start=(4, 4)), PointThreat((0, 4)))
        assert decision.action.move_type is MoveType.MOVE
        assert decision.action.direction is Direction.N

    def test_every_step_closes_the_manhattan_gap(self):
        state, threat = police(start=(4, 0)), PointThreat((0, 4))
        before = state.board.distance(state.position, threat.most_likely())
        state.apply_move(PoliceBrain().decide(state, threat).action)
        assert state.board.distance(state.position, threat.most_likely()) == before - 1

    def test_reaches_the_believed_cell_and_then_stays_on_it(self):
        state, threat = police(start=(0, 0)), PointThreat((0, 2))
        for _ in range(2):
            state.apply_move(PoliceBrain().decide(state, threat).action)
        assert state.position == (0, 2)

    def test_a_tie_is_broken_toward_an_unvisited_cell(self):
        # From (2, 2) both N and W sit three cells from (0, 0); N is already seen.
        state = police(start=(2, 2))
        state.visited.add((1, 2))
        decision = PoliceBrain().decide(state, PointThreat((0, 0)))
        assert decision.action.direction is Direction.W

    def test_rationale_names_the_believed_cell(self):
        decision = PoliceBrain().decide(police(), PointThreat((0, 1)))
        assert "(0, 1)" in decision.rationale


class TestNeverIllegal:
    def test_holds_when_walled_in(self):
        state = police()
        wall_in(state)
        decision = PoliceBrain().decide(state, PointThreat((0, 0)), barriers_max=5)
        assert decision.action.move_type is MoveType.HOLD
        assert decision.rationale == "no legal step remains"

    def test_holds_in_a_corner_sealed_by_the_board_edges(self):
        state = police(start=(0, 0))
        state.note_barrier((0, 1))
        state.note_barrier((1, 0))
        assert PoliceBrain().decide(state, PointThreat((4, 4))).action.move_type is MoveType.HOLD

    @pytest.mark.parametrize("barriers_max", [0, 3])
    def test_every_decision_is_accepted_by_the_domain_layer(self, barriers_max):
        """The contract the turn layer relies on: apply_move never rejects a decision."""
        cells = [(row, col) for row in range(5) for col in range(5)]
        for start in cells:
            for believed in cells:
                state = police(start=start)
                decision = PoliceBrain().decide(state, PointThreat(believed), barriers_max)
                assert state.apply_move(decision.action, barriers_max), (start, believed)


class TestDeterminism:
    def test_the_same_seed_always_yields_the_same_decision(self):
        """Determinism now lives in the seed, not in the absence of one: two
        brains built from identically-seeded generators must still agree."""
        state, threat = police(start=(3, 1)), PointThreat((1, 4))
        first = PoliceBrain(random.Random(7)).decide(state, threat, 5)
        second = PoliceBrain(random.Random(7)).decide(state, threat, 5)
        assert first == second

    def test_a_genuine_tie_can_resolve_differently_across_seeds(self):
        """(3, 1) -> believed (1, 4): N and E both sit at distance 4, both
        unvisited -- a real tie the old fixed-order tie-break always broke
        toward N. Enough seeds must reach both, or nothing is actually being
        randomized among the tied candidates."""
        state, threat = police(start=(3, 1)), PointThreat((1, 4))
        directions = {
            PoliceBrain(random.Random(seed)).decide(state, threat, 5).action.direction
            for seed in range(30)
        }
        assert directions == {Direction.N, Direction.E}

    def test_randomness_never_costs_movement_quality(self):
        """(4, 4) -> believed (0, 4): only N minimises the gap, no tie at all.
        No seed may ever pick anything else."""
        state, threat = police(start=(4, 4)), PointThreat((0, 4))
        for seed in range(20):
            decision = PoliceBrain(random.Random(seed)).decide(state, threat, 5)
            assert decision.action.direction is Direction.N


class TestExtensionSeam:
    def test_the_base_class_has_no_move_policy_of_its_own(self):
        state = police()
        moves = state.board.legal_moves(state.position, state.barriers)
        with pytest.raises(NotImplementedError):
            PoliceBrainBase()._pick_move(moves, state, PointThreat((0, 0)))

    def test_overriding_pick_move_changes_the_chosen_step(self):
        class FleeBrain(PoliceBrainBase):
            def _pick_move(self, moves, state, threat):
                believed = threat.most_likely()
                return max(moves, key=lambda m: state.board.distance(m[1], believed))

        state, threat = police(start=(2, 2)), PointThreat((0, 2))
        assert FleeBrain().decide(state, threat).action.direction is Direction.S
        assert PoliceBrain().decide(state, threat).action.direction is Direction.N

    def test_the_base_policy_holds_when_walled_in_without_consulting_pick_move(self):
        state = police()
        wall_in(state)
        decision = PoliceBrainBase().decide(state, PointThreat((0, 0)))
        assert decision.action.move_type is MoveType.HOLD


class TestDecision:
    def test_is_frozen_so_a_logged_decision_cannot_be_edited(self):
        decision = PoliceBrain().decide(police(), PointThreat((0, 0)))
        assert isinstance(decision, Decision)
        with pytest.raises(AttributeError):
            decision.rationale = "rewritten"
