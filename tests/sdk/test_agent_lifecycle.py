"""Runtime lifecycle (restart), and playing/persisting a match through the SDK.

Split from test_agent.py to keep both files under the project's 150-line rule.
"""

import json

import pytest

from police_agent.domain.rules import ABORTED
from police_agent.exceptions import ConfigError
from police_agent.peer.controls import GameControls
from tests.peer.fake_transport import FakeTransport, thief_turn
from tests.sdk.conftest import agent_with


def test_the_runtime_is_the_match_and_is_not_rebuilt():
    agent = agent_with()

    assert agent.runtime is agent.runtime


def test_restart_drops_the_runtime_so_the_next_access_builds_a_fresh_one():
    agent = agent_with()
    first = agent.runtime

    agent.restart()

    assert agent.runtime is not first


def test_restart_reuses_the_same_transport_rather_than_reconnecting():
    """Rebinding the port the old server still holds would fail outright."""
    agent = agent_with()
    transport = agent.connect()

    agent.restart()

    assert agent.connect() is transport
    assert agent.runtime.transport is transport


def test_play_returns_the_match_summary():
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))

    summary = agent.play()

    assert summary["role"] == "police"
    assert summary["steps"] == 1


def test_a_listener_sees_the_game_end():
    events: list[dict] = []

    agent_with(transport=FakeTransport(incoming=[thief_turn(1)]), listener=events.append).play()

    assert [event["type"] for event in events][-1] == "game_over"


def test_save_summary_writes_the_whole_record(tmp_path):
    """The report and the replay viewer are both rebuilt from this file, so a
    record trimmed to the headline result would not support either."""
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))
    summary = agent.play()

    path = agent.save_summary(summary, tmp_path / "result.json")

    assert json.loads(path.read_text(encoding="utf-8")) == summary


def test_a_saved_record_reads_back_for_the_replay_player(tmp_path):
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))
    path = agent.save_summary(agent.play(), tmp_path / "result.json")

    assert agent.load_summary(path)["role"] == "police"


def test_a_missing_log_names_the_file_rather_than_raising_an_os_error():
    agent = agent_with()

    with pytest.raises(ConfigError, match="Match log not found"):
        agent.load_summary("nowhere/result.json")


def test_a_log_that_is_not_json_says_so(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="not valid JSON"):
        agent_with().load_summary(path)


def test_controls_reach_the_runtime_so_the_windows_buttons_are_real():
    """The GUI cannot pass these at construction -- it needs an SDK to build its
    window from before it has a window to steer with -- so they are settable."""
    controls = GameControls()
    controls.stop()
    agent = agent_with(transport=FakeTransport(incoming=[thief_turn(1)]))
    agent.controls = controls

    assert agent.play()["result"] == ABORTED
