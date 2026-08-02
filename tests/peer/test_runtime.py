"""The turn loop end to end, driven by a scripted thief."""

import pytest

from police_agent.domain.rules import CAPTURE, SURVIVAL, TAMPER_FORFEIT, TECHNICAL_LOSS, TIMEOUT
from police_agent.peer.protocol import AuditPayload, TurnMessage
from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn, thief_turns


def run_against(incoming, audit=None, **overrides):
    """Play one sub-game against a scripted thief and return (summary, transport)."""
    transport = FakeTransport(incoming=incoming, audit=audit)
    summary = PoliceRuntime(config_with(**overrides), transport).run()
    return summary, transport


def test_the_police_waits_before_it_moves():
    """The thief opens, so nothing may be sent until a turn has arrived."""
    _, transport = run_against([])

    assert transport.sent_turns == []
    assert transport.agreement_sent is not None  # but the handshake did happen


def test_a_confirmed_capture_claim_ends_the_game():
    summary, _ = run_against(
        [thief_turn(1), thief_turn(2, claim_response={"claim": [1, 0], "caught": True})]
    )

    assert (summary["result"], summary["winner"]) == (CAPTURE, "police")


def test_the_police_claims_the_cell_it_stepped_onto():
    """From (0,0) with no scent yet, the chase heads for the board centre.

    N and W are off-board and S and E are equidistant from (3,3), so the fixed
    N/S/E/W tie-break takes S to (1,0) -- and the claim must be that same cell,
    not the one it came from.
    """
    summary, transport = run_against([thief_turn(1)])

    sent = TurnMessage.from_dict(transport.sent_turns[0])
    assert sent.capture_claim == [1, 0]
    assert summary["my_log"][0]["position"] == [1, 0]
    assert (sent.sender, sent.step) == ("police", 1)


def test_a_silent_opponent_forfeits():
    """An empty script is a peer that stopped answering."""
    summary, _ = run_against([thief_turn(1)])

    assert (summary["result"], summary["winner"]) == (TECHNICAL_LOSS, "police")


def test_a_survival_claim_at_the_threshold_is_honoured():
    summary, _ = run_against(
        [thief_turn(3, win_claim={"type": "survival"})],
        rules__max_steps=3,
        rules__survival_threshold=3,
    )

    assert (summary["result"], summary["winner"]) == (SURVIVAL, "thief")


def test_an_early_survival_claim_is_disputed_not_conceded():
    summary, _ = run_against(
        [thief_turn(1, win_claim={"type": "survival"})],
        rules__max_steps=4,
        rules__survival_threshold=4,
    )

    assert summary["result"] != SURVIVAL
    assert "survival claimed at step 1" in summary["disputes"][0]


def test_reaching_the_ceiling_short_of_the_threshold_expires():
    summary, _ = run_against(thief_turns(4), rules__max_steps=2, rules__survival_threshold=99)

    assert (summary["result"], summary["winner"]) == (TIMEOUT, None)


def test_a_forged_opponent_log_forfeits_the_game():
    """A capture the police won is overridden when the thief's reveal will not hash."""
    forged = AuditPayload(
        sender="thief",
        records=[{"payload": {"step": 1}, "nonce": "n", "commit": "not-the-real-digest"}],
        result_claim="capture",
    ).to_dict()

    summary, _ = run_against(
        [thief_turn(1), thief_turn(2, claim_response={"caught": True})], audit=forged
    )

    assert (summary["result"], summary["winner"]) == (TAMPER_FORFEIT, "police")
    assert summary["audit"]["passed"] is False


def test_the_police_seals_one_record_per_turn_it_played():
    summary, transport = run_against([thief_turn(1), thief_turn(2)])

    assert len(summary["records"]) == len(transport.sent_turns) == 2
    assert all(record["commit"] for record in summary["records"])


def test_every_sealed_record_verifies_against_its_own_commit():
    """The audit this peer would face: its own log must survive it."""
    from police_agent.domain.crypto import audit_records

    summary, _ = run_against(thief_turns(3))

    assert audit_records(summary["records"])["passed"] is True


def test_the_commit_on_the_wire_is_the_commit_of_the_record():
    summary, transport = run_against([thief_turn(1)])

    assert transport.sent_turns[0]["commit"] == summary["records"][0]["commit"]


def test_the_true_position_never_crosses_the_wire():
    _, transport = run_against(thief_turns(3))

    for message in transport.sent_turns:
        assert "position" not in message
        assert "nonce" not in message


def test_progress_events_reach_a_listener():
    events = []
    transport = FakeTransport(incoming=[thief_turn(1)])
    PoliceRuntime(config_with(), transport, listener=events.append).run()

    assert [event["type"] for event in events][:2] == ["negotiated", "incoming"]
    assert events[-1]["type"] == "game_over"


def test_a_missing_agreed_term_is_refused_before_any_play():
    from police_agent.exceptions import ConfigError

    with pytest.raises(ConfigError, match="board_size"):
        PoliceRuntime(config_with(board__size=None), FakeTransport())
