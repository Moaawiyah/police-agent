"""The replay stepper: rebuilding a match from its log, without a display."""

from police_agent.domain.crypto import CommitReveal
from police_agent.gui.replay import ReplayApp
from police_agent.strategy.belief import BeliefGrid
from tests.conftest import config_with
from tests.gui.fake_window import FakeWindow


def sealed(step: int) -> dict:
    payload = {"step": step, "position": [step, 0], "rationale": f"step {step}"}
    return {"payload": payload, **CommitReveal.seal(payload)}


def log_of(steps: int, smell: dict | None = None) -> dict:
    """A police log of `steps` moves south from the corner, with the thief heard."""
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "audit": {"passed": True, "verified_steps": steps},
        "opponent_reliability": 0.5,
        "records": [sealed(step) for step in range(1, steps + 1)],
        "history": [
            {"step": step, "hint": f"hint {step}", "smell_grid": smell or {}}
            for step in range(1, steps + 1)
        ],
        "my_log": [
            {"step": step, "position": [step, 0], "barrier": None} for step in range(1, steps + 1)
        ],
    }


def player(log: dict, opponent=None) -> tuple[ReplayApp, FakeWindow]:
    window = FakeWindow()
    return ReplayApp(config_with(), log, opponent_log=opponent, window=window), window


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
    app, window = player(log)

    app.advance()

    assert "TAMPERED" in window.labels["commit"]
    assert "Verification FAILED" in window.labels["status"]


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
    theirs = {
        "records": [sealed(1), sealed(2)],
        "my_log": [{"position": [3, 3]}, {"position": [3, 4]}],
        "audit": {"passed": True},
    }
    app, window = player(log_of(2), opponent=theirs)

    app.advance()

    assert window.views[-1]["opponent_position"] == (3, 3)
    assert window.views[-1]["opponent_role"] == "thief"
    assert "Verified OK" in window.labels["status"]
    assert "both agents shown" in window.labels["status"]


def test_without_the_opponent_log_the_board_says_so():
    app, window = player(log_of(2))

    app.advance()

    assert window.views[-1]["opponent_position"] is None
    assert "not supplied" in window.labels["status"]


def test_failed_audit_is_never_labelled_verified():
    app, window = player({**log_of(1), "audit": {"passed": False}})

    app.advance()

    assert window.labels["status"].startswith("step 1/1 | Verification FAILED")


def test_a_tampered_opponent_log_fails_cross_log_verification():
    their_record = sealed(1)
    their_record["payload"]["position"] = [6, 6]
    theirs = {
        "records": [their_record],
        "my_log": [{"position": [6, 6]}],
        "audit": {"passed": True},
    }
    app, window = player(log_of(1), opponent=theirs)

    app.advance()

    assert "Verification FAILED" in window.labels["status"]


def test_playback_runs_to_the_longer_track_and_freezes_the_shorter():
    """Whoever ended the game took the last turn, so the two logs rarely match."""
    theirs = {"my_log": [{"position": [3, col]} for col in range(4)]}
    app, window = player(log_of(2), opponent=theirs)

    for _ in range(4):
        app.advance()

    assert len(window.views) == 4
    assert window.views[-1]["position"] == (2, 0)  # frozen on its last logged cell
    assert "police track ended" in window.views[-1]["message"]


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
