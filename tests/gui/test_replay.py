"""The replay stepper: rebuilding a match from its log, without a display.

Board/opponent drawing lives in `test_replay_board.py`, and navigation
(restart, goto, edge cases) in `test_replay_navigation.py` -- split out to
keep each file under the project's line budget, sharing `replay_helpers.py`.
"""

from police_agent.strategy.belief import BeliefGrid
from tests.conftest import config_with
from tests.gui.replay_helpers import log_of, player


def test_one_step_draws_the_position_that_was_logged():
    app, window = player(log_of(3))

    app.advance()

    assert window.views[-1]["position"] == (1, 0)
    assert window.views[-1]["step"] == 1


def test_stepping_accumulates_the_trail():
    app, window = player(log_of(3))

    app.advance()
    app.advance()

    assert window.views[-1]["visited"] == {(1, 0), (2, 0)}


def test_the_belief_is_rebuilt_from_the_recorded_scent_not_read_back():
    """This is what makes the replay evidence: the heatmap follows from the log
    by the same BeliefGrid the agent played with, or it visibly disagrees."""
    app, window = player(log_of(3, smell={"3,3": 0.9}))

    app.advance()

    belief = window.views[-1]["belief"]
    assert belief[3][3] == max(cell for row in belief for cell in row)


def test_a_log_with_no_scent_still_predicts_but_observes_nothing():
    """A log missing its smell history must open rather than refuse: the commit
    re-verification is the part that carries weight. What is left is the predict
    step plus an empty observation, which is the same thing the agent's own
    belief did that turn (turn_handler always calls observe_smell, even on an
    empty grid, and the leak inside it still applies)."""
    expected = BeliefGrid(config_with().require("board.size"))
    expected.diffuse()
    expected.observe_smell({})
    app, window = player(log_of(2))

    app.advance()

    assert window.views[-1]["belief"] == expected.as_matrix()


def test_each_step_re_verifies_its_own_commit():
    app, window = player(log_of(2))

    app.advance()

    assert "verified OK" in window.labels["commit"]
    assert window.labels["verdict"] == "step 1 (revealed)"


def test_a_rewritten_log_is_caught_as_it_is_drawn():
    log = log_of(2)
    log["records"][0]["payload"]["position"] = [6, 6]
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

    assert "TAMPERED" in window.labels["commit"]
