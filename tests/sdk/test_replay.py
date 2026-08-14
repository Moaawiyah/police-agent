"""Reading a saved log back: normalisation and commit re-verification.

Label/position rendering (`move_labels`, `opponent_positions`,
`frozen_message`) lives in `test_replay_labels.py`, split out to keep both
files under the project's line budget.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.sdk.replay import TAMPERED, VERIFIED, normalize_log, verify_record


def sealed(step: int, rationale: str = "closing in") -> dict:
    payload = {"step": step, "position": [step, 0], "rationale": rationale}
    return {"payload": payload, **CommitReveal.seal(payload)}


def our_log(**overrides) -> dict:
    """A summary in the shape `save_summary` writes: everything at the top level."""
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "group_name": "police-team",
        "duration_seconds": 9.0,
        "audit": {"passed": True, "verified_steps": 2},
        "opponent_reliability": 0.75,
        "records": [sealed(1), sealed(2)],
        "history": [{"step": 1, "hint": "over here", "smell_grid": {"3,3": 0.9}}],
        "my_log": [{"step": 1, "position": [1, 0], "barrier": None}],
    }


def test_our_own_log_reads_back_whole():
    view = normalize_log(our_log())

    assert view["role"] == "police"
    assert view["winner"] == "police"
    assert view["group"] == "police-team"
    assert len(view["records"]) == 2
    assert view["reliability"] == 0.75


def test_the_sub_game_number_is_read_from_the_top_level_when_present():
    log = {**our_log(), "sub_game_number": 4}

    assert normalize_log(log)["sub_game_number"] == 4


def test_a_log_with_no_sub_game_number_falls_back_to_one():
    assert normalize_log({})["sub_game_number"] == 1


def test_a_log_nested_under_summary_reads_the_same_way():
    """The course reference nests it, and the league has us replay another
    group's log -- a player that could only open its own proves nothing."""
    nested = {"game_id": "x", "summary": our_log()}

    assert normalize_log(nested)["group"] == "police-team"
    assert len(normalize_log(nested)["records"]) == 2


def test_records_at_the_top_level_are_found_even_when_the_summary_omits_them():
    nested = {"summary": {"role": "thief"}, "records": [sealed(1)]}

    view = normalize_log(nested)

    assert view["role"] == "thief"
    assert len(view["records"]) == 1


def test_production_police_artifact_recovers_moves_and_messages():
    artifact = {
        "artifact_type": "sub_game_log",
        "roles": {"police": "police-team", "thief": "thief-team"},
        "records": [sealed(1)],
        "opponent_messages": [{"step": 1, "hint": "north"}],
    }

    view = normalize_log(artifact)

    assert view["group"] == "police-team"
    assert view["my_log"] == [{"step": 1, "position": [1, 0], "barrier": None}]
    assert view["history"] == [{"step": 1, "hint": "north"}]


def test_production_thief_artifact_recovers_moves_and_winner_role():
    artifact = {
        "summary": {
            "role": "thief",
            "group_id": "thief-team",
            "winner_role": "police",
            "audit": {"passed": True},
        },
        "records": [sealed(1)],
    }

    view = normalize_log(artifact)

    assert view["group"] == "thief-team"
    assert view["winner"] == "police"
    assert view["my_log"][0]["position"] == [1, 0]


def test_an_empty_log_opens_instead_of_refusing():
    """A log without a smell history replays with a flat belief; the commit
    re-verification is the part that carries weight and it still runs."""
    view = normalize_log({})

    assert view["history"] == []
    assert view["my_log"] == []
    assert view["winner"] == "nobody"
    assert view["audit"]["passed"] is True


def test_a_group_that_only_named_itself_group_id_is_still_named():
    assert normalize_log({"group_id": "other-team"})["group"] == "other-team"


def test_an_honest_record_re_verifies():
    assert verify_record([sealed(1)], 0) == VERIFIED


def test_a_rewritten_payload_is_caught():
    """This is the whole point of the player: the audit is recomputed in front
    of the viewer rather than read back out of the same file that was edited."""
    record = sealed(1)
    record["payload"]["position"] = [6, 6]

    assert verify_record([record], 0) == TAMPERED


def test_a_record_missing_its_nonce_fails_like_any_other():
    record = sealed(1)
    del record["nonce"]

    assert verify_record([record], 0) == TAMPERED


def test_a_step_past_the_end_of_the_log_claims_nothing():
    assert verify_record([sealed(1)], 5) == "-"
