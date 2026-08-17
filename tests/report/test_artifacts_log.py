"""The sub-game log artifact: what the replay simulator re-verifies from it,
and its deliberately asymmetric per-peer agreement digest.

Split from test_artifacts.py to keep both files under the project's 150-line
rule; fixtures are defined there and imported here.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.peer.step_zero import sealed_step_zero
from police_agent.report.artifacts import LOG_TYPE, build_log, roles_of
from police_agent.report.facts import facts_from
from police_agent.report.ids import SCHEMA_VERSION, consensus_signature
from tests.conftest import config_with
from tests.report.test_artifacts import A_TURN, ANOTHER_TURN, POLICE, THIEF, _summary


class TestTheSubGameLogArtifact:
    def test_it_names_itself_the_schema_and_the_sub_game(self):
        artifact = _log()

        assert artifact["artifact_type"] == LOG_TYPE
        assert artifact["schema_version"] == SCHEMA_VERSION
        assert artifact["sub_game_number"] == 2

    def test_it_reports_how_the_sub_game_ended(self):
        artifact = _log()

        assert (artifact["result"], artifact["winner"]) == ("capture", "police")
        assert artifact["steps"] == 2
        assert artifact["duration_seconds"] == 4.2

    def test_it_says_which_group_played_which_side(self):
        """Group-keyed, not role-keyed: matches the sibling thief repo's own
        convention, so an independently written opponent's `roles` block
        hashes the same way for `mutual_agreement.sha256`."""
        assert _log()["roles"] == {POLICE: "police", THIEF: "thief"}

    def test_the_sides_are_read_from_the_record_because_roles_alternate(self):
        """This peer is only the police in the sub-games where it is."""
        swapped = roles_of({**_summary(), "role": "thief"})

        assert swapped == {POLICE: "thief", THIEF: "police"}

    def test_every_turn_is_carried_with_its_nonce_and_hash(self):
        """Without both, the replay simulator can re-read the log but not check it."""
        artifact = _log()

        assert artifact["records"] == [A_TURN, ANOTHER_TURN]

    def test_the_declaration_is_carried_whole_and_out_of_the_turn_list(self):
        """A payload alone would be a claim about the seal, not the seal itself."""
        declaration = sealed_step_zero(config_with())
        summary = {**_summary(), "records": [declaration, A_TURN]}

        artifact = build_log(facts_from(summary), summary)

        CommitReveal.verify(
            artifact["step_zero"]["payload"],
            artifact["step_zero"]["nonce"],
            artifact["step_zero"]["commit"],
        )
        assert artifact["records"] == [A_TURN]

    def test_a_log_written_without_a_declaration_reports_it_absent(self):
        assert _log()["step_zero"] == {}

    def test_it_carries_the_verbal_layer_the_replay_needs(self):
        artifact = _log()

        assert artifact["opponent_messages"] == [{"step": 1, "hint": "north of you"}]
        assert artifact["hint_readings"] == ["step 1: agreed with the trail"]
        assert artifact["opponent_reliability"] == 0.75

    def test_it_carries_the_evidence_the_gate_and_the_ledger_produced(self):
        artifact = _log()

        assert artifact["tokens"]["tokens_total"] == 120
        assert artifact["gatekeeper"]["sent"] == 3

    def test_an_ordinary_result_carries_no_abort_reason(self):
        assert _log()["abort_reason"] is None

    def test_a_watchdog_abort_carries_its_reason_into_the_log(self):
        """The only artifact a watchdog trip's diagnosis survives into -- it
        is peer-local and never crosses the wire, so it cannot appear in the
        symmetric result artifact (report/result.py)."""
        summary = {**_summary(), "result": "aborted", "abort_reason": "watchdog: unresponsive 200s"}

        assert build_log(facts_from(summary), summary)["abort_reason"] == summary["abort_reason"]

    def test_a_summary_missing_its_optional_blocks_still_builds(self):
        """The report of a match that failed early is the one the grader needs."""
        artifact = build_log(facts_from({}), {})

        assert artifact["records"] == []
        assert artifact["audit"] == {}
        assert artifact["mutual_agreement"]["confirmed"] is False


class TestTheLogsDeliberatelyAsymmetricAgreement:
    def test_it_confirms_only_when_the_audit_passed(self):
        assert _log()["mutual_agreement"]["confirmed"] is True

    def test_the_digest_is_over_this_peers_own_records(self):
        """So the two peers' values differ by design, and it is not a bug: the log
        is one peer's testimony, and a digest matching theirs would mean we had
        hashed something other than what we are testifying to."""
        summary = _summary()

        digest = build_log(facts_from(summary), summary)["mutual_agreement"]["sha256"]

        assert digest == consensus_signature({"records": summary["records"]})

    def test_editing_a_single_sealed_turn_changes_it(self):
        summary = {**_summary(), "records": [A_TURN, {**ANOTHER_TURN, "commit": "forged"}]}

        edited = build_log(facts_from(summary), summary)["mutual_agreement"]["sha256"]

        assert edited != _log()["mutual_agreement"]["sha256"]

    def test_it_says_in_the_file_itself_why_the_two_sides_differ(self):
        """It looks like a bug, and somebody will otherwise 'fix' it."""
        assert "symmetric" in _log()["mutual_agreement"]["_remark"]


def _log() -> dict:
    return build_log(facts_from(_summary()), _summary())
