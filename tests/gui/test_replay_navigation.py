"""Ending, restarting and jumping through a replayed match, plus its edge
cases, split out of test_replay.py to keep both files under the project's
line budget.
"""

from tests.gui.replay_helpers import log_of, player


def test_the_end_of_the_log_announces_the_result_instead_of_stepping():
    app, window = player(log_of(1))

    app.advance()
    app.advance()

    assert window.banner == (False, "REPLAY DONE: capture - winner POLICE")
    assert len(window.views) == 1


def test_restart_returns_to_an_empty_board_and_a_flat_belief():
    app, window = player(log_of(3, smell={"3,3": 0.9}))
    app.advance()
    app.advance()

    app.restart()

    assert window.views[-1]["visited"] == set()
    assert window.views[-1]["step"] == 0
    belief = window.views[-1]["belief"]
    assert len({round(cell, 9) for row in belief for cell in row}) == 1


def test_jumping_replays_from_the_start_because_the_belief_has_no_way_back():
    app, window = player(log_of(4, smell={"3,3": 0.9}))

    app.goto(3)

    assert window.views[-1]["step"] == 3
    assert window.views[-1]["visited"] == {(1, 0), (2, 0), (3, 0)}


def test_jumping_past_the_end_stops_at_the_end():
    app, window = player(log_of(2))

    app.goto(99)

    assert window.views[-1]["step"] == 2


def test_jumping_below_the_first_step_still_plays_one():
    app, window = player(log_of(2))

    app.goto(0)

    assert window.views[-1]["step"] == 1


def test_an_empty_log_opens_and_reports_that_there_is_nothing_to_show():
    app, window = player({"result": "aborted", "winner": None})

    app.advance()

    assert window.views == []
    assert window.banner[1].startswith("REPLAY DONE")


def test_the_recorded_reliability_is_shown_and_a_missing_one_is_not_invented():
    _, with_score = player(log_of(1))
    log = log_of(1)
    del log["opponent_reliability"]
    _, without = player(log)

    assert with_score.labels["reliability"] == "0.50"
    assert without.labels["reliability"] == "-"
