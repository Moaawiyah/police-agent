"""The study entry point writes its figures and data where it is told to."""

import json

import research.__main__ as study
from research.grid import BELIEF, STRATEGY


def _sandbox(tmp_path, monkeypatch):
    """Redirect both outputs into tmp_path so a test cannot touch real artifacts."""
    monkeypatch.setattr(study, "DATA", tmp_path / "research-data.json")
    monkeypatch.setattr("research.plots.ASSETS", tmp_path / "assets")
    return tmp_path / "research-data.json"


def test_every_swept_name_is_a_real_parameter():
    from research.sweeps import BELIEF_PARAMS, STRATEGY_TARGETS

    assert set(BELIEF) <= set(BELIEF_PARAMS)
    assert set(STRATEGY) <= set(STRATEGY_TARGETS)


def test_every_range_brackets_the_shipped_value():
    # A range that only looked upward could not tell a good default from an untried one.
    for values, shipped in list(BELIEF.values()) + list(STRATEGY.values()):
        assert min(values) <= shipped <= max(values)
        assert shipped in values, f"{shipped} must itself be a measured point"


def test_main_writes_the_data_file_and_the_figures(tmp_path, monkeypatch):
    data = _sandbox(tmp_path, monkeypatch)
    assert study.main(["2"]) == 0
    collected = json.loads(data.read_text())
    assert collected["episodes"] == 2
    assert set(collected["belief"]) == set(BELIEF)
    assert set(collected["strategy"]) == set(STRATEGY)
    figures = list((tmp_path / "assets").glob("*.png"))
    assert len(figures) == 2 * len(BELIEF) + len(STRATEGY)


def test_main_defaults_to_the_configured_episode_count(tmp_path, monkeypatch):
    data = _sandbox(tmp_path, monkeypatch)
    monkeypatch.setattr(study, "EPISODES", 1)
    monkeypatch.setattr(study, "run", lambda episodes: {"episodes": episodes})
    assert study.main([]) == 0
    assert json.loads(data.read_text())["episodes"] == 1


def test_a_recorded_row_carries_its_interval(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch)
    collected = study.run(2)
    row = collected["belief"]["leak"]["points"][0]
    assert row["ci95"][0] <= row["capture_rate"] <= row["ci95"][1]
