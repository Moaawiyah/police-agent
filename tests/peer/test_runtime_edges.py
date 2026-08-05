"""Turn-loop paths that only appear when something goes wrong or unusually right."""

from police_agent.constants import Direction, MoveType
from police_agent.domain.actions import barrier, move
from police_agent.domain.rules import CAPTURE, SURVIVAL
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.step_zero import turn_records
from police_agent.peer.summary import SKIPPED_AUDIT
from police_agent.strategy.decision import Decision
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn, thief_turns


class FixedBrain:
    """A brain that always returns the same action, legal or not."""

    def __init__(self, action) -> None:
        self.action = action

    def decide(self, state, threat, barriers_max):
        return Decision(self.action, "fixed for the test")


def test_an_illegal_action_from_the_strategy_becomes_a_hold():
    """N from (0,0) is off-board. The loop must survive a broken brain."""
    transport = FakeTransport(incoming=[thief_turn(1)])
    summary = PoliceRuntime(config_with(), transport, brain=FixedBrain(move(Direction.N))).run()

    assert summary["my_log"][0]["position"] == [0, 0]  # it did not move
    assert "illegal action" in turn_records(summary["records"])[0]["payload"]["rationale"]
    assert turn_records(summary["records"])[0]["payload"]["move"] == "HOLD:-"


def test_a_held_turn_is_still_sealed_and_still_sent():
    transport = FakeTransport(incoming=[thief_turn(1)])
    PoliceRuntime(config_with(), transport, brain=FixedBrain(move(Direction.N))).run()

    assert len(transport.sent_turns) == 1
    assert transport.sent_turns[0]["commit"]


def test_placing_a_barrier_makes_no_capture_claim():
    """The police did not move, so re-claiming its own cell would waste the turn."""
    transport = FakeTransport(incoming=[thief_turn(1)])
    PoliceRuntime(config_with(), transport, brain=FixedBrain(barrier(Direction.E))).run()

    sent = transport.sent_turns[0]
    assert sent["capture_claim"] is None
    assert sent["barrier_placed"] == [0, 1]  # declared in the clear, as it must be


def test_the_strategy_walls_a_cornered_thief_over_the_real_loop():
    """End to end: scent puts the thief in a corner, the shipped brain walls it."""
    transport = FakeTransport(
        incoming=[thief_turn(1, smell_grid={"0,0": 0.9})],
    )
    summary = PoliceRuntime(config_with(positions__cop_start=[0, 2]), transport).run()

    assert summary["barriers_used"] == 1
    assert transport.sent_turns[0]["barrier_placed"] == [0, 1]


def test_reaching_the_ceiling_at_the_threshold_is_a_survival():
    transport = FakeTransport(incoming=thief_turns(6))
    summary = PoliceRuntime(
        config_with(rules__max_steps=2, rules__survival_threshold=2), transport
    ).run()

    assert (summary["result"], summary["winner"]) == (SURVIVAL, "thief")


def test_an_opponent_that_never_reveals_leaves_the_board_result_standing():
    """Nothing is proven either way, so a capture is not upgraded or thrown away."""
    transport = FakeTransport(
        incoming=[thief_turn(1), thief_turn(2, claim_response={"caught": True})], audit=None
    )
    summary = PoliceRuntime(config_with(), transport).run()

    assert (summary["result"], summary["winner"]) == (CAPTURE, "police")
    assert summary["audit"] == SKIPPED_AUDIT
    assert summary["audit"]["skipped"] is True


def test_a_forfeited_game_does_not_wait_on_an_audit_that_cannot_come():
    """The opponent already went silent; asking it to reveal only costs a timeout."""
    transport = FakeTransport(incoming=[])
    summary = PoliceRuntime(config_with(), transport).run()

    assert transport.sent_audits == []
    assert summary["audit"] == SKIPPED_AUDIT


def test_the_barrier_quota_is_taken_from_the_agreed_terms():
    transport = FakeTransport(incoming=thief_turns(3))
    runtime = PoliceRuntime(config_with(rules__barriers_max=2), transport)

    assert runtime.barriers_max == 2


def test_a_non_move_action_type_is_reported_faithfully_in_the_record():
    transport = FakeTransport(incoming=[thief_turn(1)])
    summary = PoliceRuntime(config_with(), transport, brain=FixedBrain(barrier(Direction.S))).run()

    assert turn_records(summary["records"])[0]["payload"]["barrier"] == [1, 0]
    assert MoveType.BARRIER.value in turn_records(summary["records"])[0]["payload"]["move"]
