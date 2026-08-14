"""The turn loop end to end, driven by a scripted thief.

Tamper/forfeit detection and record sealing live in `test_runtime_audit.py`;
progress events, config validation and the belief log in
`test_runtime_belief.py` -- split out to keep each file under the project's
line budget, sharing `runtime_helpers.py`'s `run_against`.
"""

from police_agent.domain.rules import SURVIVAL, TECHNICAL_LOSS
from police_agent.peer.protocol import TurnMessage
from tests.peer.fake_transport import thief_turn, thief_turns
from tests.peer.runtime_helpers import run_against


def test_the_police_waits_before_it_moves():
    """The thief opens, so nothing may be sent until a turn has arrived."""
    _, transport = run_against([])

    assert transport.sent_turns == []
    assert transport.agreement_sent is not None  # but the handshake did happen


def test_a_confirmed_capture_without_a_reveal_becomes_a_technical_win():
    summary, _ = run_against(
        [thief_turn(1), thief_turn(2, claim_response={"claim": [1, 0], "caught": True})]
    )

    assert (summary["result"], summary["winner"]) == (TECHNICAL_LOSS, "police")


def test_the_police_claims_the_cell_it_stepped_onto():
    """From (0,0) with no scent yet, the chase heads for the board centre.

    N and W are off-board and S and E are equidistant from (3,3), so either is
    a legal first step -- which one is no longer fixed (movement ties are now
    broken randomly, see strategy/brain.py). What must hold regardless is that
    the claim names wherever the police actually stepped, not the cell it left.
    """
    summary, transport = run_against([thief_turn(1)])

    sent = TurnMessage.from_dict(transport.sent_turns[0])
    stepped_to = summary["my_log"][0]["position"]
    assert stepped_to in ([1, 0], [0, 1])  # S or E: the only two legal ties from (0,0)
    assert sent.capture_claim == stepped_to
    assert (sent.sender, sent.step) == ("police", 1)


def test_a_silent_opponent_forfeits():
    """An empty script is a peer that stopped answering."""
    summary, _ = run_against([thief_turn(1)])

    assert (summary["result"], summary["winner"]) == (TECHNICAL_LOSS, "police")


def test_a_survival_claim_without_a_reveal_becomes_a_technical_win():
    summary, _ = run_against(
        [thief_turn(3, win_claim={"type": "survival"})],
        rules__max_steps=3,
        rules__survival_threshold=3,
    )

    assert (summary["result"], summary["winner"]) == (TECHNICAL_LOSS, "police")


def test_the_police_still_plays_its_matching_final_move_before_conceding_survival():
    """A real match hit exactly this: the thief's step-35 message carried both
    its last move and the survival claim, so the police conceded one move short
    of the thief's own count (34 logged steps against the thief's 35).

    That final move is recorded locally only, never sent: a self-verified
    survival claim never waits for a reply, so a transmitted message here
    would sit unread in a transport a series holds open across sub-games --
    and be mistaken for the next sub-game's opening turn."""
    summary, transport = run_against(
        [thief_turn(1), thief_turn(2), thief_turn(3, win_claim={"type": "survival"})],
        rules__max_steps=3,
        rules__survival_threshold=3,
    )

    assert summary["steps"] == 3
    assert len(transport.sent_turns) == 2


def test_an_early_survival_claim_is_disputed_not_conceded():
    summary, _ = run_against(
        [thief_turn(1, win_claim={"type": "survival"})],
        rules__max_steps=4,
        rules__survival_threshold=4,
    )

    assert summary["result"] != SURVIVAL
    assert "survival claimed at step 1" in summary["disputes"][0]


def test_a_timeout_without_a_reveal_becomes_a_technical_win():
    summary, _ = run_against(thief_turns(4), rules__max_steps=2, rules__survival_threshold=99)

    assert (summary["result"], summary["winner"]) == (TECHNICAL_LOSS, "police")
