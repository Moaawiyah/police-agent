"""Folding the thief's messages into the police's own view."""

from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import GameRules
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.turn_handler import TurnHandler
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.bluff import BluffAnalyst, Verdict
from tests.peer.fake_transport import thief_turn


def handler(max_steps: int = 10, survival: int = 10, threat=None, analyst=None) -> TurnHandler:
    threat = threat if threat is not None else BeliefGrid(7)
    return TurnHandler(OwnGameState((0, 0), 7), threat, GameRules(max_steps, survival), analyst)


class RecordingThreat:
    """A belief that only remembers the order it was called in."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def diffuse(self, barriers=None) -> None:
        self.calls.append("diffuse")

    def observe_smell(self, cells) -> None:
        self.calls.append("observe_smell")

    def scale(self, cells, factor) -> None:
        self.calls.append("scale")

    def most_likely(self):
        return (0, 0)


def process(subject: TurnHandler, **fields):
    return subject.process(TurnMessage.from_dict(thief_turn(fields.pop("step", 1), **fields)))


def test_a_confirmed_claim_is_a_win():
    assert process(handler(), claim_response={"caught": True}).i_won is True


def test_an_answered_but_denied_claim_is_not_a_win():
    assert process(handler(), claim_response={"caught": False}).i_won is False


def test_a_survival_claim_at_the_threshold_is_accepted():
    outcome = process(handler(survival=4), step=4, win_claim={"type": "survival"})

    assert outcome.opponent_won is True
    assert outcome.disputes == []


def test_a_survival_claim_below_the_threshold_is_disputed():
    outcome = process(handler(survival=9), step=2, win_claim={"type": "survival"})

    assert outcome.opponent_won is False
    assert "threshold is 9" in outcome.disputes[0]


def test_an_unrecognised_win_claim_is_disputed_not_obeyed():
    outcome = process(handler(), win_claim={"type": "i_simply_win"})

    assert outcome.opponent_won is False
    assert "unknown win claim" in outcome.disputes[0]


def test_scent_updates_what_the_police_will_chase():
    subject = handler()
    process(subject, smell_grid={"5,5": 0.9, "1,1": 0.2})

    assert subject.threat.most_likely() == (5, 5)


def test_the_belief_is_spread_before_the_fresh_scent_sharpens_it():
    """A message proves the thief moved, so predicting must precede observing."""
    recorder = RecordingThreat()
    process(handler(threat=recorder), smell_grid={"5,5": 0.9})

    assert recorder.calls == ["diffuse", "observe_smell"]


def test_the_analyst_judges_the_hint_against_the_trail_that_arrived_with_it():
    """It needs the hint, the prior belief, and the freshest smelled cell."""
    seen = {}

    class Analyst:
        def assess(self, hint, believed, smelled):
            seen.update(hint=hint, believed=believed, smelled=smelled)
            return Verdict()

        def apply(self, verdict, belief, origin):
            pass

    subject = TurnHandler(
        OwnGameState((0, 0), 7), BeliefGrid(7), GameRules(10, 10), analyst=Analyst()
    )
    process(subject, smell_grid={"5,5": 0.9, "1,1": 0.2}, hint="gone north")

    prior = BeliefGrid(7)
    prior.diffuse()  # what the belief was after the thief moved, before it smelled

    assert seen["hint"] == "gone north"
    assert seen["smelled"] == (5, 5)  # the strongest cell, not merely the grid
    assert seen["believed"] == prior.most_likely()  # the prior the trail revises


def test_what_was_made_of_each_hint_is_kept_for_the_report():
    subject = handler(analyst=BluffAnalyst())
    process(subject, step=1, smell_grid={"5,5": 0.9}, hint="I went north")

    assert "step 1" in subject.readings[0]


def test_hints_are_ignored_entirely_when_no_analyst_is_configured():
    subject = handler()
    process(subject, hint="I went north")

    assert subject.readings == []


def test_a_declared_barrier_is_recorded_even_from_the_thief():
    """Barriers are police-only, but one declared is impassable for both sides."""
    subject = handler()
    process(subject, barrier_placed=[2, 2])

    assert (2, 2) in subject.state.barriers


def test_the_recorded_barrier_is_respected_by_the_next_prediction():
    """A barrier declared this turn must already block the diffuse it triggers."""
    subject = handler()
    process(subject, step=1, smell_grid={"3,3": 0.9})

    process(subject, step=2, barrier_placed=[2, 3])

    matrix = subject.threat.as_matrix()
    assert matrix[2][3] < matrix[4][3]  # blocked neighbour lost out to the open one


def test_every_message_is_kept_for_the_replay():
    subject = handler()
    process(subject, step=1)
    process(subject, step=2)

    assert [entry["step"] for entry in subject.history] == [1, 2]
