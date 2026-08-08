"""The agreed-config artifact: what goes into its digest and what changes it.

The sub-game log artifact -- the replay-facing one -- lives in
test_artifacts_log.py, split out to keep both files under the project's
150-line rule; fixtures are defined here and imported there.
"""

from police_agent.report.artifacts import CONFIG_TYPE, build_config
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


def _config() -> dict:
    return build_config(facts_from(_summary()), _summary())


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
