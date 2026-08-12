"""Reading a saved log back: normalisation, re-verification, labels."""

from police_agent.domain.crypto import CommitReveal
from police_agent.sdk.replay import (
    TAMPERED,
    VERIFIED,
    frozen_message,
    move_labels,
    normalize_log,
    opponent_positions,
    verify_record,
)


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


def test_the_step_panel_shows_the_revealed_reason_and_the_verdict():
    record = sealed(1, "cornering toward the wall")

    labels = move_labels(record, VERIFIED)

    assert labels["verdict"] == "cornering toward the wall (revealed)"
    assert labels["commit"].endswith(f"... [{VERIFIED}]")
    assert record["commit"][:32] in labels["commit"]


def test_a_record_with_no_payload_still_labels_something():
    labels = move_labels({}, "-")

    assert labels["verdict"] == "- (revealed)"


def test_the_opponents_positions_come_from_its_own_revealed_log():
    """Unknowable during play; simply history once both peers have revealed."""
    theirs = {"my_log": [{"position": [3, 3]}, {"position": [3, 4]}]}

    assert opponent_positions(theirs) == [[3, 3], [3, 4]]


def test_no_opponent_log_means_no_second_marker():
    assert opponent_positions(None) == []
    assert opponent_positions({}) == []


def test_nothing_is_frozen_while_both_tracks_still_run():
    assert frozen_message(0, 5, 5) is None


def test_a_track_that_ran_out_is_named_so_it_does_not_read_as_a_stall():
    assert "police" in frozen_message(5, 5, 9)
    assert "thief" in frozen_message(5, 9, 5)


def test_both_can_be_frozen_at_once():
    message = frozen_message(9, 5, 5)

    assert "police" in message and "thief" in message


def test_a_missing_opponent_log_never_freezes_the_thief():
    """Zero opponent steps means we do not have its log, not that it stopped."""
    assert frozen_message(9, 20, 0) is None
