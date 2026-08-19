"""The three sources a peer's commit can come from, and their priority.

An out-of-band pin is a value we were TOLD, not one we were sent, so the two
wire sources must both outrank it and it must apply only to the named opponent
and the role it actually played.
"""

from police_agent.report.peer_commits import PINNED_COMMITS, commits_of, pinned_commit

WIRE = "1111111111111111111111111111111111111111"
SEALED = "2222222222222222222222222222222222222222"
THEIR_THIEF = PINNED_COMMITS["cosmos77"]["thief"]
THEIR_POLICE = PINNED_COMMITS["cosmos77"]["police"]


def summary(peer: dict, role: str = "police", records: list | None = None) -> dict:
    return {
        "identity": {"group_id": "MOAAMOHA", "github_commit": "ours"},
        "peer_identity": {"group_id": "cosmos77", **peer},
        "role": role,
        "opponent_records": records or [],
    }


def sealed(commit: str) -> list:
    return [{"payload": {"step": 0, "record_type": "step_zero", "github_commit": commit}}]


class TestPriority:
    def test_the_handshake_identity_wins_over_everything(self):
        got = commits_of(summary({"github_commit": WIRE}, records=sealed(SEALED)))

        assert got["cosmos77"] == WIRE

    def test_the_sealed_record_wins_over_the_pin(self):
        """Tamper-checked at the audit, so it outranks anything we were told."""
        got = commits_of(summary({}, records=sealed(SEALED)))

        assert got["cosmos77"] == SEALED

    def test_the_pin_fills_the_gap_when_the_wire_carried_nothing(self):
        got = commits_of(summary({}))

        assert got["cosmos77"] == THEIR_THIEF

    def test_our_own_commit_is_never_taken_from_the_pin(self):
        got = commits_of(summary({}))

        assert got["MOAAMOHA"] == "ours"


class TestTheRoleTheyActuallyPlayed:
    """Roles alternate, and each of their two repos has its own commit."""

    def test_our_police_sub_game_pins_their_thief_repo(self):
        assert commits_of(summary({}, role="police"))["cosmos77"] == THEIR_THIEF

    def test_our_thief_sub_game_pins_their_cop_repo(self):
        assert commits_of(summary({}, role="thief"))["cosmos77"] == THEIR_POLICE


class TestAnUnpinnedOpponent:
    def test_a_team_we_have_no_pin_for_still_reports_empty(self):
        """Never borrow another team's commit to fill a blank."""
        assert pinned_commit("someone-else", "thief") == ""

    def test_an_unknown_role_is_not_guessed(self):
        assert pinned_commit("cosmos77", "") == ""
