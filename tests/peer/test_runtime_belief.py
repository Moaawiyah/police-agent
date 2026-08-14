"""Progress events, config validation and the belief log, split out of
test_runtime.py to keep both files under the project's line budget.
"""

import pytest

from police_agent.exceptions import ConfigError
from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn
from tests.peer.runtime_helpers import run_against


def test_progress_events_reach_a_listener():
    events = []
    transport = FakeTransport(incoming=[thief_turn(1)])
    PoliceRuntime(config_with(), transport, listener=events.append).run()

    assert [event["type"] for event in events][:2] == ["negotiated", "incoming"]
    assert events[-1]["type"] == "game_over"


def test_a_missing_agreed_term_is_refused_before_any_play():
    with pytest.raises(ConfigError, match="board_size"):
        PoliceRuntime(config_with(board__size=None), FakeTransport())


def test_the_belief_log_records_one_bayes_update_per_incoming_turn():
    """Scent grid plus the posterior it produced, one entry per thief turn --
    not per step of the game, since a replayed/duplicate turn folds nothing in."""
    summary, _ = run_against([thief_turn(1, smell_grid={"3,3": 0.9}), thief_turn(2)])

    assert [entry["step"] for entry in summary["belief_log"]] == [1, 2]
    assert summary["belief_log"][0]["smell_grid"] == {"3,3": 0.9}
    matrix = summary["belief_log"][0]["belief"]
    assert len(matrix) == len(matrix[0]) == config_with().require("board.size")
    assert abs(sum(sum(row) for row in matrix) - 1.0) < 1e-9  # still a distribution


def test_a_replayed_turn_does_not_add_a_second_belief_log_entry():
    summary, _ = run_against([thief_turn(1), thief_turn(1)])  # same step twice

    assert len(summary["belief_log"]) == 1
