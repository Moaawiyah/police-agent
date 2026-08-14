"""Barriers and the opponent track in a replayed match, split out of
test_replay.py to keep both files under the project's line budget.
"""

from tests.gui.replay_helpers import log_of, player


def test_a_barrier_in_the_log_stays_on_the_board():
    log = log_of(2)
    log["my_log"][0]["barrier"] = [1, 1]
    app, window = player(log)

    app.advance()
    app.advance()

    assert (1, 1) in window.views[-1]["barriers"]


def test_a_barrier_the_thief_declared_is_drawn_too():
    """A barrier is impassable for both peers, so both sides' walls are real."""
    log = log_of(2)
    log["history"][0]["barrier_placed"] = [4, 4]
    app, window = player(log)

    app.advance()

    assert (4, 4) in window.views[-1]["barriers"]


def test_the_opponent_is_drawn_only_when_its_revealed_log_was_supplied():
    theirs = {"my_log": [{"position": [3, 3]}, {"position": [3, 4]}]}
    app, window = player(log_of(2), opponent=theirs)

    app.advance()

    assert window.views[-1]["opponent_position"] == (3, 3)
    assert window.views[-1]["opponent_role"] == "thief"
    assert "both agents shown" in window.labels["status"]


def test_without_the_opponent_log_the_board_says_so():
    app, window = player(log_of(2))

    app.advance()

    assert window.views[-1]["opponent_position"] is None
    assert "not supplied" in window.labels["status"]


def test_playback_runs_to_the_longer_track_and_freezes_the_shorter():
    """Whoever ended the game took the last turn, so the two logs rarely match."""
    theirs = {"my_log": [{"position": [3, col]} for col in range(4)]}
    app, window = player(log_of(2), opponent=theirs)

    for _ in range(4):
        app.advance()

    assert len(window.views) == 4
    assert window.views[-1]["position"] == (2, 0)  # frozen on its last logged cell
    assert "police track ended" in window.views[-1]["message"]
