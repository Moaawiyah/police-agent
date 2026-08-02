"""Replay protection: an old valid turn must not be playable twice.

The attack this closes is cheap and does not need a forged message. Every turn
the police accepts draws a reply, so an opponent that simply echoes one genuine
turn back could march this peer through its whole move budget while never moving
itself -- and each echo would diffuse the belief another step, blurring it away
from a thief that had not moved at all.

A duplicate is dropped rather than punished. The transport retries outbound
calls, so a repeat is at least as likely to be our own network as an opponent.
"""

from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import TECHNICAL_LOSS, GameRules
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.turn_handler import TurnHandler
from police_agent.strategy.belief import BeliefGrid
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn


class RecordingThreat:
    """A belief that only remembers whether the turn loop touched it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def diffuse(self) -> None:
        self.calls.append("diffuse")

    def observe_smell(self, cells) -> None:
        self.calls.append("observe_smell")

    def most_likely(self):
        return (0, 0)


def handler(threat=None) -> TurnHandler:
    threat = threat if threat is not None else BeliefGrid(7)
    return TurnHandler(OwnGameState((0, 0), 7), threat, GameRules(10, 10))


def process(subject: TurnHandler, step: int = 1, **fields):
    return subject.process(TurnMessage.from_dict(thief_turn(step, **fields)))


class TestTheHandlerDropsRepeats:
    def test_the_first_arrival_of_a_turn_is_played_normally(self):
        assert process(handler()).replayed is False

    def test_the_same_turn_arriving_twice_is_played_once(self):
        subject = handler()
        process(subject, step=1)

        assert process(subject, step=1).replayed is True

    def test_a_repeat_is_reported_rather_than_swallowed(self):
        subject = handler()
        process(subject, step=1)

        outcome = process(subject, step=1)

        assert "step 1" in outcome.disputes[0]

    def test_a_repeat_changes_nothing_it_touches(self):
        recorder = RecordingThreat()
        subject = handler(threat=recorder)
        process(subject, step=1, barrier_placed=[3, 3])
        process(subject, step=1, barrier_placed=[3, 3])

        assert recorder.calls == ["diffuse", "observe_smell"]  # folded in once
        assert len(subject.history) == 1

    def test_genuine_turns_keep_flowing(self):
        subject = handler()

        assert [process(subject, step=step).replayed for step in (1, 2, 3)] == [False] * 3
        assert len(subject.history) == 3


class TestTheIdentityIsTheCommitment:
    def test_rewriting_the_step_does_not_launder_a_spent_turn(self):
        """The step is inside the sealed payload, so the commit outranks it."""
        subject = handler()
        process(subject, step=1, commit="abc123")

        assert process(subject, step=9, commit="abc123").replayed is True

    def test_two_genuine_turns_are_told_apart_by_their_commitments(self):
        subject = handler()
        process(subject, step=1, commit="abc123")

        assert process(subject, step=1, commit="def456").replayed is False

    def test_a_peer_that_sends_no_commitment_still_gets_verbatim_protection(self):
        """Not committing breaks the protocol, but is no reason to stop guarding."""
        subject = handler()
        process(subject, step=1, commit="")

        assert process(subject, step=1, commit="").replayed is True
        assert process(subject, step=2, commit="").replayed is False

    def test_a_confirmed_capture_cannot_be_claimed_twice(self):
        subject = handler()
        confirmation = {"claim": [1, 0], "caught": True}

        assert process(subject, step=1, claim_response=confirmation).i_won is True
        assert process(subject, step=1, claim_response=confirmation).i_won is False


class TestTheRuntimeDoesNotReplyToARepeat:
    def test_an_echoed_turn_does_not_buy_the_opponent_another_move(self):
        """The exploit: one genuine turn echoed back should not walk us forward."""
        echoed = thief_turn(1)
        transport = FakeTransport(incoming=[echoed, dict(echoed), dict(echoed)])

        summary = PoliceRuntime(config_with(), transport).run()

        assert len(transport.sent_turns) == 1
        assert summary["result"] == TECHNICAL_LOSS  # it went quiet, so it forfeited

    def test_the_repeat_is_carried_into_the_report(self):
        echoed = thief_turn(1)
        transport = FakeTransport(incoming=[echoed, dict(echoed)])

        summary = PoliceRuntime(config_with(), transport).run()

        assert any("already-played" in dispute for dispute in summary["disputes"])

    def test_an_ordinary_match_is_untouched_by_the_guard(self):
        transport = FakeTransport(incoming=[thief_turn(1), thief_turn(2), thief_turn(3)])

        PoliceRuntime(config_with(), transport).run()

        assert len(transport.sent_turns) == 3
