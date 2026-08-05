"""The two per-sub-game files: the terms signed, and the turns played under them.

The config artifact's whole value is its digest, so the tests that matter are the
ones about what goes into it and what changes it. The log's are about
completeness: a replay simulator handed this file must be able to re-verify every
commitment in it without the match record it was projected from.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.peer.step_zero import sealed_step_zero
from police_agent.report.artifacts import (
    CONFIG_TYPE,
    LOG_TYPE,
    build_config,
    build_log,
    roles_of,
)
from police_agent.report.facts import facts_from
from police_agent.report.ids import SCHEMA_VERSION, canonical_sha256, consensus_signature
from tests.conftest import config_with

POLICE, THIEF = "police-team", "thief-team"
TERMS = {"board_size": 7, "max_steps": 35}
A_TURN = {"payload": {"step": 1, "move": "MOVE:S"}, "nonce": "n1", "commit": "c1"}
ANOTHER_TURN = {"payload": {"step": 2, "move": "MOVE:E"}, "nonce": "n2", "commit": "c2"}


class TestTheAgreedConfigArtifact:
    def test_it_names_itself_the_schema_and_the_sub_game(self):
        artifact = _config()

        assert artifact["artifact_type"] == CONFIG_TYPE
        assert artifact["schema_version"] == SCHEMA_VERSION
        assert artifact["sub_game_number"] == 2

    def test_it_carries_the_identifiers_the_four_files_are_joined_on(self):
        facts = facts_from(_summary())

        artifact = build_config(facts, _summary())

        assert (artifact["game_uid"], artifact["game_id"]) == (facts.game_uid, facts.game_id)

    def test_it_lists_both_groups_sorted_so_either_peer_writes_the_same_line(self):
        assert _config()["agreed_between"] == [POLICE, THIEF]

    def test_it_hashes_the_whole_agreed_file_when_one_was_loaded(self):
        """Ch. 9.2 loads game.json byte-identically on both sides precisely so it
        can be hashed consistently -- the lecturer compares files, not handshakes."""
        config = config_with()

        artifact = build_config(facts_from(_summary()), _summary(), config)

        assert artifact["config"] == config.shared
        assert artifact["config_sha256"] == canonical_sha256(config.shared)

    def test_the_verified_handshake_subset_stands_in_when_no_file_is_to_hand(self):
        """Degraded but never absent: a missing hash reads as a missing agreement."""
        artifact = _config()

        assert artifact["config"] == TERMS
        assert artifact["config_sha256"] == canonical_sha256(TERMS)

    def test_a_match_that_agreed_nothing_still_produces_a_hashable_block(self):
        artifact = build_config(facts_from({}), {})

        assert artifact["config"] == {}
        assert artifact["config_sha256"]

    def test_changing_one_agreed_value_changes_the_digest(self):
        summary = _summary()
        other = {**summary, "terms": {**TERMS, "board_size": 9}}

        assert build_config(facts_from(other), other)["config_sha256"] != _config()["config_sha256"]

    def test_the_digest_uses_the_compact_form_every_commitment_uses(self):
        """`report/ids.py`'s trap: the spacious form would hash plausibly, pass
        every test here, and disagree with the opposing team's recomputation."""
        artifact = _config()

        assert artifact["config_sha256"] != consensus_signature(artifact["config"])


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
        assert _log()["roles"] == {"police": POLICE, "thief": THIEF}

    def test_the_sides_are_read_from_the_record_because_roles_alternate(self):
        """This peer is only the police in the sub-games where it is."""
        swapped = roles_of({**_summary(), "role": "thief"})

        assert swapped == {"thief": POLICE, "police": THIEF}

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


def _config() -> dict:
    return build_config(facts_from(_summary()), _summary())


def _log() -> dict:
    return build_log(facts_from(_summary()), _summary())


def _summary() -> dict:
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "steps": 2,
        "duration_seconds": 4.2,
        "identity": {"group_id": POLICE},
        "peer_identity": {"group_id": THIEF},
        "terms": TERMS,
        "step_zero": {"sub_game_number": 2},
        "started_at": "2026-08-05T09:00:00+00:00",
        "ended_at": "2026-08-05T09:02:00+00:00",
        "records": [A_TURN, ANOTHER_TURN],
        "history": [{"step": 1, "hint": "north of you"}],
        "hint_readings": ["step 1: agreed with the trail"],
        "opponent_reliability": 0.75,
        "disputes": [],
        "tokens": {"tokens_total": 120},
        "gatekeeper": {"sent": 3},
        "audit": {"passed": True, "verified_steps": 3, "failed_steps": []},
    }
