"""The declaration made before the first move, and why it is binding.

Rules 24 and 53 are one object here (ch. 5.5), so these tests check two separate
things: that the payload says everything the chapter lists, and that it cannot
be rewritten afterwards to say something more flattering. The second is the part
that actually matters -- a declaration written at the end of a match a peer lost
would be worth nothing.
"""

from police_agent.domain.crypto import CommitReveal, audit_records
from police_agent.exceptions import CryptoError
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.step_zero import (
    RECORD_TYPE,
    STEP_ZERO,
    is_step_zero,
    sealed_step_zero,
    step_zero_of,
    turn_records,
)
from tests.conftest import STUB_COMMIT, STUB_SPEC, config_with
from tests.peer.fake_transport import FakeTransport, thief_turn, thief_turns

A_TURN = {"payload": {"step": 1, "move": "MOVE:S"}, "nonce": "n", "commit": "c"}


class TestWhatTheChapterAsksForIsThere:
    def test_it_declares_the_machine_it_is_playing_on(self):
        """Rule 24: OS, CPU cores and clock, RAM, GPU and VRAM (ch. 5.5)."""
        spec = sealed_step_zero(config_with())["payload"]["hardware_spec"]

        assert spec == STUB_SPEC

    def test_it_declares_the_commit_being_played(self):
        """Rule 53: the grader must be able to check this revision out."""
        payload = sealed_step_zero(config_with())["payload"]

        assert payload["github_commit"] == STUB_COMMIT
        assert payload["working_tree_dirty"] is False

    def test_it_declares_the_code_version_group_and_sub_game(self):
        payload = sealed_step_zero(config_with(game__sub_game_number=3))["payload"]

        assert payload["code_version"]
        assert payload["group_name"] == "unnamed"  # game.json carries no identity
        assert payload["sub_game_number"] == 3

    def test_it_names_the_language_model_the_verbal_layer_uses(self):
        payload = sealed_step_zero(config_with(llm__model="some-model"))["payload"]

        assert payload["llm_model"] == "some-model"

    def test_it_sorts_ahead_of_every_turn(self):
        payload = sealed_step_zero(config_with())["payload"]

        assert payload["step"] == STEP_ZERO
        assert payload["record_type"] == RECORD_TYPE


class TestItCannotBeRewrittenAfterwards:
    def test_it_is_sealed_like_any_other_record(self):
        record = sealed_step_zero(config_with())

        CommitReveal.verify(record["payload"], record["nonce"], record["commit"])

    def test_editing_the_declared_hardware_breaks_its_own_commit(self):
        """The whole point of ch. 5.5: a losing peer cannot restate its machine."""
        record = sealed_step_zero(config_with())
        record["payload"]["hardware_spec"]["cpu_cores"] = 128

        try:
            CommitReveal.verify(record["payload"], record["nonce"], record["commit"])
        except CryptoError:
            return
        raise AssertionError("a tampered declaration verified")

    def test_the_digest_is_handed_over_before_the_first_move(self):
        """Published at the handshake, so the reveal cannot be a later invention."""
        transport = FakeTransport(incoming=[thief_turn(1)])
        runtime = PoliceRuntime(config_with(), transport)
        declared = runtime.records[0]["commit"]
        runtime.run()

        assert transport.agreement_sent["identity"]["step_zero_commit"] == declared

    def test_the_opponent_receives_it_in_the_audit_reveal(self):
        summary, _ = _play([thief_turn(1)])

        assert is_step_zero(summary["records"][0])
        assert summary["records"][0]["nonce"]  # the nonce it needs to recompute

    def test_a_tampered_declaration_fails_the_log_audit_as_step_zero(self):
        summary, _ = _play([thief_turn(1)])
        summary["records"][0]["payload"]["github_commit"] = "a-nicer-commit"

        result = audit_records(summary["records"])

        assert result["passed"] is False
        assert result["failed_steps"] == [STEP_ZERO]


class TestItDoesNotDisturbTheTurns:
    def test_the_declaration_heads_the_log_and_the_turns_follow(self):
        summary, transport = _play(thief_turns(3))

        assert is_step_zero(summary["records"][0])
        assert len(turn_records(summary["records"])) == len(transport.sent_turns)

    def test_the_step_count_still_counts_moves_only(self):
        summary, _ = _play(thief_turns(3))

        assert summary["steps"] == 3

    def test_an_honest_log_still_passes_its_own_audit(self):
        summary, _ = _play(thief_turns(2))

        assert audit_records(summary["records"])["passed"] is True

    def test_the_summary_exposes_the_payload_for_the_report(self):
        summary, _ = _play([thief_turn(1)])

        assert summary["step_zero"]["github_commit"] == STUB_COMMIT


class TestReadingSomebodyElsesLog:
    def test_a_turn_is_not_mistaken_for_a_declaration(self):
        assert is_step_zero(A_TURN) is False

    def test_records_are_recognised_by_content_not_position(self):
        """Applied to the opponent's log too, where we control neither."""
        declaration = sealed_step_zero(config_with())

        assert turn_records([A_TURN, declaration]) == [A_TURN]

    def test_an_opponent_with_no_declaration_is_reported_absent_not_raised_on(self):
        """Their rule-24 problem, and no reason to abandon a playable match."""
        assert step_zero_of([A_TURN]) == {}
        assert step_zero_of([]) == {}
        assert turn_records(None) == []

    def test_junk_in_a_revealed_log_is_survived(self):
        assert is_step_zero({"payload": "not a dict"}) is False
        assert is_step_zero({}) is False


def _play(incoming):
    transport = FakeTransport(incoming=incoming)
    return PoliceRuntime(config_with(), transport).run(), transport
