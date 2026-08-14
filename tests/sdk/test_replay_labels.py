"""Label and position rendering for a replayed log, split out of
test_replay.py to keep both files under the project's line budget.
"""

from police_agent.sdk.replay import VERIFIED, frozen_message, move_labels, opponent_positions
from tests.sdk.test_replay import sealed


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
