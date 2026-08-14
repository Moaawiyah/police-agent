"""Identifiers and digests two peers derive separately and must still agree on.

Nothing here is exchanged over the wire, so every property is a claim about
arithmetic done twice on two machines. The symmetry tests matter most: they are
what proves neither peer needs to be told the answer.

`ReportFacts` -- the shared read-out of a match record built on top of these
ids -- is tested in `test_facts.py`, split out to keep both files under the
project's line budget.
"""

import uuid

from police_agent.report.ids import (
    canonical_sha256,
    consensus_signature,
    game_id,
    game_uid,
    links,
    sub_game_tag,
)

TERMS = {"board_size": 7, "max_steps": 35}
POLICE, THIEF = "police-team", "thief-team"


class TestTheMatchName:
    def test_it_is_the_two_group_ids_sorted(self):
        assert game_id(POLICE, THIEF) == "police-team-vs-thief-team"

    def test_either_peer_derives_the_same_name(self):
        """Neither side is told it; both compute it and must land together."""
        assert game_id(POLICE, THIEF) == game_id(THIEF, POLICE)


class TestTheMatchUid:
    def test_it_is_a_real_uuid(self):
        uuid.UUID(game_uid(TERMS, POLICE, THIEF))  # raises if it is not

    def test_either_peer_derives_the_same_uid(self):
        assert game_uid(TERMS, POLICE, THIEF) == game_uid(TERMS, THIEF, POLICE)

    def test_different_agreed_terms_are_a_different_game(self):
        """A rematch on other terms must not be filed under the same uid."""
        other = game_uid({**TERMS, "board_size": 9}, POLICE, THIEF)

        assert other != game_uid(TERMS, POLICE, THIEF)

    def test_the_terms_hash_does_not_depend_on_key_order(self):
        reordered = {"max_steps": 35, "board_size": 7}

        assert game_uid(reordered, POLICE, THIEF) == game_uid(TERMS, POLICE, THIEF)


class TestTheTwoCanonicalForms:
    def test_they_disagree_on_the_very_same_input(self):
        """The trap this module exists to keep visible.

        They differ only in JSON whitespace, so a swapped pair still returns a
        plausible digest and every test of our own artifacts still passes. The
        only symptom is the opposing team recomputing a different value.
        """
        data = {"a": 1, "b": [2, 3]}

        assert consensus_signature(data) != canonical_sha256(data)

    def test_each_form_hashes_the_bytes_it_claims_to(self):
        """Literals, not recomputation: re-deriving them here would prove nothing.

        `{"a": 1}` with a space for the schema signatures, `{"a":1}` without one
        for the commitments. These two digests are the whole contract with the
        opposing team's parser.
        """
        assert (
            consensus_signature({"a": 1})
            == "f9d86028c6e0d64e225186f96acb69338b2c59764df79162107f5c4bb34d1310"
        )
        assert (
            canonical_sha256({"a": 1})
            == "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
        )

    def test_both_are_stable_across_key_order(self):
        first, second = {"a": 1, "b": 2}, {"b": 2, "a": 1}

        assert consensus_signature(first) == consensus_signature(second)
        assert canonical_sha256(first) == canonical_sha256(second)

    def test_changing_any_value_changes_both(self):
        base, edited = {"score": 20}, {"score": 5}

        assert consensus_signature(base) != consensus_signature(edited)
        assert canonical_sha256(base) != canonical_sha256(edited)


class TestFilenamesAndLinks:
    def test_the_sub_game_tag_is_zero_padded(self):
        assert (sub_game_tag(1), sub_game_tag(12)) == ("g01", "g12")

    def test_every_filename_carries_the_game_id(self):
        block = links("a-vs-b")

        assert all("a-vs-b" in block[role] for role in ("declaration", "config", "log", "result"))

    def test_the_per_sub_game_entries_stay_a_placeholder(self):
        """The block describes the whole family, not the file it sits in."""
        block = links("a-vs-b")

        assert block["config"] == "config_a-vs-b_g<NN>.json"
        assert block["log"] == "log_a-vs-b_g<NN>.json"
