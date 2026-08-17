"""The pre-game declaration: what holds across the whole series, and only that.

Two properties are worth defending here. The first is that the artifact describes
*both* groups, because the lecturer's tooling joins the two teams' files on it and
a declaration that only knew itself would be half a document. The second is that
nothing which changes between sub-games leaks in -- roles alternate, so a role or
a sub-game number in this file would be false for half the series.

The hardware projection and the per-group signature live in
`test_declaration_signing.py`, split out to keep both files under the
project's line budget.
"""

from police_agent.report.declaration import (
    DECLARATION_TYPE,
    UNKNOWN,
    build_declaration,
    group_block,
)
from police_agent.report.facts import facts_from
from police_agent.report.ids import SCHEMA_VERSION
from tests.conftest import STUB_SPEC

POLICE, THIEF = "police-team", "thief-team"

OUR_IDENTITY = {
    "group_id": POLICE,
    "group_name": "Police Team",
    "members": ["id-1001", "id-1002"],
    "repos": {"cop": "https://example.test/cop", "thief": "https://example.test/thief"},
    "mcp_servers": {"cop": "https://cops.ngrok.app/mcp"},
    "llm_model": "qwen3:4b",
    "code_version": "1.00",
    "hardware_spec": STUB_SPEC,
    "github_commit": "0" * 40,
}
THEIR_IDENTITY = {**OUR_IDENTITY, "group_id": THIEF, "group_name": "Thief Team"}


class TestWhatTheChapterPinsBeforeTheSeries:
    def test_it_names_itself_and_the_schema_it_follows(self):
        artifact = _declaration()

        assert artifact["declaration_type"] == DECLARATION_TYPE
        assert artifact["schema_version"] == SCHEMA_VERSION

    def test_it_carries_the_identifiers_the_four_files_are_joined_on(self):
        facts = facts_from(_summary())

        artifact = build_declaration(facts, _summary())

        assert artifact["game_id"] == facts.game_id
        assert artifact["game_uid"] == facts.game_uid

    def test_it_carries_the_links_block_so_a_reader_can_find_the_others(self):
        artifact = _declaration()

        assert artifact["links"]["result"] == f"result_{artifact['game_id']}.json"

    def test_it_pins_the_series_length_the_ceiling_and_the_clock(self):
        artifact = _declaration()

        assert artifact["num_sub_games"] == 3
        assert artifact["max_tokens_per_game"] == 200000
        assert artifact["game_started_at"] == "2026-08-05T09:00:00+00:00"
        assert artifact["game_ended_at"] == "2026-08-05T09:02:00+00:00"
        assert artifact["timezone"]

    def test_counted_games_played_defaults_to_zero(self):
        artifact = _declaration()

        assert artifact["counted_games_played"] == 0

    def test_counted_games_played_is_exclusive_of_this_one(self):
        """The declaration is filed before the sub-games are played, so it
        reports how many prior series are on record -- not this one."""
        facts = facts_from(_summary())

        artifact = build_declaration(facts, _summary(), counted_games_played=3)

        assert artifact["counted_games_played"] == 3

    def test_nothing_that_changes_between_sub_games_appears(self):
        """Roles alternate across the series, so either would be false by game 2.

        The prose `_schema` note says the same thing in words, so this looks at
        the keys rather than the rendered file.
        """
        artifact = _declaration()
        keys = set(artifact) | set(artifact["groups"]["group_1"])

        assert not keys & {"role", "sub_game_number", "result", "winner"}


class TestBothGroupsAreDescribed:
    def test_group_one_is_us_and_group_two_is_the_opponent(self):
        groups = _declaration()["groups"]

        assert groups["group_1"]["group_id"] == POLICE
        assert groups["group_2"]["group_id"] == THIEF

    def test_the_opponent_is_described_from_what_it_sent_at_the_handshake(self):
        """The only moment either peer learns anything at all about the other."""
        block = _declaration()["groups"]["group_2"]

        assert block["group_name"] == "Thief Team"
        assert block["repos"] == THEIR_IDENTITY["repos"]
        assert block["mcp_servers"] == THEIR_IDENTITY["mcp_servers"]
        assert block["llm_model"] == "qwen3:4b"

    def test_an_opponent_that_declared_nothing_is_reported_unknown_not_guessed(self):
        """Its rule-24 problem. Inventing plausible hardware would make it ours."""
        artifact = build_declaration(facts_from({"identity": OUR_IDENTITY}), {})

        block = artifact["groups"]["group_2"]
        assert block["group_name"] == UNKNOWN
        assert block["llm_model"] == UNKNOWN
        assert set(block["hardware_spec"].values()) == {UNKNOWN}

    def test_an_absent_group_still_has_the_schemas_shape(self):
        """A parser on the other side should not have to branch on our silence."""
        block = group_block({})

        assert block["members"] == []
        assert block["repos"] == {}
        assert len(block["hardware_spec"]) == 6


def _declaration() -> dict:
    return build_declaration(facts_from(_summary()), _summary())


def _summary() -> dict:
    return {
        "identity": OUR_IDENTITY,
        "peer_identity": THEIR_IDENTITY,
        "terms": {"board_size": 7, "num_games": 3},
        "started_at": "2026-08-05T09:00:00+00:00",
        "ended_at": "2026-08-05T09:02:00+00:00",
        "tokens": {"budget_per_series": 200000},
    }
