"""Tests for the terminal conditions the police can evaluate on its own."""

from police_agent.domain.actions import hold
from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import GameRules


def rules(max_steps=35, survival_threshold=35):
    return GameRules(max_steps=max_steps, survival_threshold=survival_threshold)


def police(start=(0, 0)):
    return OwnGameState(start=start, board_size=7)


class TestStepCeiling:
    def test_a_fresh_game_is_not_out_of_steps(self):
        assert not rules().out_of_steps(police())

    def test_ceiling_is_reached_exactly_on_the_last_step(self):
        state = police()
        game_rules = rules(max_steps=2)
        state.apply_move(hold())
        assert not game_rules.out_of_steps(state)
        state.apply_move(hold())
        assert game_rules.out_of_steps(state)


class TestSurvivalClaim:
    """The thief raises the claim; the police checks it against the agreed terms."""

    def test_claim_below_the_threshold_is_rejected(self):
        assert not rules(survival_threshold=35).thief_survived(34)

    def test_claim_exactly_at_the_threshold_holds(self):
        assert rules(survival_threshold=35).thief_survived(35)

    def test_claim_beyond_the_threshold_holds(self):
        assert rules(survival_threshold=35).thief_survived(36)

    def test_threshold_is_independent_of_the_step_ceiling(self):
        game_rules = rules(max_steps=50, survival_threshold=35)
        assert game_rules.thief_survived(35)
        assert not game_rules.out_of_steps(police())
