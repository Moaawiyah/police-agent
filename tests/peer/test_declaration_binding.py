"""Holding the opponent to the declaration it published before the first move.

`audit_records` only proves the opponent's revealed declaration hashes to the
commit stored beside it -- a peer that rewrote both still passes that. What
settles it is the digest it handed over at the handshake, while the match was
still unplayed. These tests are about that second check, and they speak the
sibling thief's `system_spec` spelling throughout: the binding is worth nothing
if it only recognises our own record shape.
"""

from police_agent.domain.crypto import CommitReveal, audit_records
from police_agent.domain.rules import TAMPER_FORFEIT
from police_agent.peer.protocol import AuditPayload
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.step_zero import STEP_ZERO, audit_declaration
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn

A_TURN = {"payload": {"step": 1, "move": "MOVE:S"}, "nonce": "n", "commit": "c"}


def thief_declaration(group: str = "thief-team") -> dict:
    """A step-zero record in the sibling thief repository's own spelling."""
    payload = {"step": STEP_ZERO, "type": "system_spec", "group_name": group}
    return {"payload": payload, **CommitReveal.seal(payload)}


class PublishingPeer(FakeTransport):
    """A thief that publishes a step-zero digest in its handshake identity."""

    def __init__(self, digest: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._digest = digest

    def exchange_agreement(self, signed: dict) -> dict:
        """Echo the police's own agreement, but with this peer's declaration digest."""
        echoed = super().exchange_agreement(signed)
        identity = {**echoed.get("identity", {}), "step_zero_commit": self._digest}
        return {**echoed, "identity": identity}


class TestWhatItAccepts:
    def test_an_opponent_that_published_no_digest_is_not_accused(self):
        """Their rule-24 problem, not a forgery we can prove -- and refusing the
        audit over it would reject every peer predating the field."""
        audit = {"passed": True, "failed_steps": []}

        assert audit_declaration(audit, [A_TURN], {}) == []
        assert audit == {"passed": True, "failed_steps": []}

    def test_the_declaration_it_promised_is_the_one_it_revealed(self):
        declaration = thief_declaration()
        audit = {"passed": True, "failed_steps": []}

        disputes = audit_declaration(
            audit, [declaration, A_TURN], {"step_zero_commit": declaration["commit"]}
        )

        assert disputes == []
        assert audit["passed"] is True

    def test_a_declaration_it_could_still_swap_is_no_defence(self):
        """The swapped record hashes correctly on its own -- which is exactly
        why the record-level audit cannot be the check that catches it."""
        swapped = thief_declaration("someone-else")

        assert audit_records([swapped])["passed"] is True


class TestWhatItRejects:
    def test_a_swapped_declaration_fails_the_audit_as_step_zero(self):
        published = thief_declaration()["commit"]
        audit = {"passed": True, "failed_steps": []}

        disputes = audit_declaration(
            audit, [thief_declaration("someone-else")], {"step_zero_commit": published}
        )

        assert len(disputes) == 1 and "declaration" in disputes[0]
        assert audit["passed"] is False
        assert audit["failed_steps"] == [STEP_ZERO]

    def test_promising_a_declaration_and_revealing_none_fails_too(self):
        audit = {"passed": True, "failed_steps": []}

        disputes = audit_declaration(
            audit, [A_TURN], {"step_zero_commit": thief_declaration()["commit"]}
        )

        assert len(disputes) == 1 and "revealed no declaration" in disputes[0]
        assert audit["failed_steps"] == [STEP_ZERO]

    def test_it_does_not_lose_the_failures_the_hashes_already_found(self):
        audit = {"passed": False, "failed_steps": [4]}

        audit_declaration(audit, [A_TURN], {"step_zero_commit": "a-digest"})

        assert audit["failed_steps"] == [4, STEP_ZERO]


class TestOverAWholeSubGame:
    def test_a_forged_declaration_forfeits_the_match(self):
        published = thief_declaration()["commit"]
        revealed = AuditPayload(
            sender="thief",
            records=[thief_declaration("someone-else")],
            result_claim="capture",
        ).to_dict()
        transport = PublishingPeer(
            published,
            incoming=[thief_turn(1), thief_turn(2, claim_response={"caught": True})],
            audit=revealed,
        )

        summary = PoliceRuntime(config_with(), transport).run()

        assert (summary["result"], summary["winner"]) == (TAMPER_FORFEIT, "police")
        assert STEP_ZERO in summary["audit"]["failed_steps"]
        assert any("declaration" in dispute for dispute in summary["disputes"])
