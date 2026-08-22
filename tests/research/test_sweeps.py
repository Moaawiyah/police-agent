"""The sweep drivers patch the right binding site and restore it afterwards."""

import pytest

import police_agent.strategy.barrier as barrier_module
import police_agent.strategy.brain as brain_module
from research.harness import Episode
from research.sweeps import aggregate, patched, sweep_belief, sweep_strategy


def _episodes(*captured):
    return [Episode("capture" if c else "survival", "claim", 10, 5, 10, 0.5) for c in captured]


def test_aggregate_reports_the_capture_rate_and_the_batch_size():
    point = aggregate(1.0, _episodes(True, True, False, False))
    assert point.capture_rate == 0.5
    assert point.episodes == 4


def test_the_confidence_interval_narrows_as_episodes_are_added():
    few = aggregate(1.0, _episodes(*([True, False] * 10)))
    many = aggregate(1.0, _episodes(*([True, False] * 100)))
    assert many.capture_se < few.capture_se
    low, high = many.capture_ci95
    assert low < many.capture_rate < high


def test_the_interval_is_clamped_to_a_valid_probability():
    certain = aggregate(1.0, _episodes(*([True] * 5)))
    assert certain.capture_ci95 == (1.0, 1.0)


def test_patched_rebinds_at_the_module_that_actually_binds_the_constant():
    # brain.py imports TOP_K by value, so patching placement would not reach it.
    original = brain_module.TOP_K
    with patched("TOP_K", 99):
        assert brain_module.TOP_K == 99
    restored = brain_module.TOP_K
    assert restored == original


def test_patched_restores_the_original_even_when_the_body_raises():
    original = barrier_module.WIDE_REACH
    with pytest.raises(RuntimeError), patched("WIDE_REACH", 0):
        raise RuntimeError("boom")
    restored = barrier_module.WIDE_REACH
    assert restored == original


def test_an_unknown_belief_parameter_is_refused():
    with pytest.raises(ValueError, match="is not a belief parameter"):
        sweep_belief("nonsense", [1.0], episodes=1)


def test_an_unknown_strategy_constant_is_refused():
    with pytest.raises(ValueError, match="is not a strategy constant"):
        sweep_strategy("nonsense", [1.0], episodes=1)


def test_a_belief_sweep_returns_one_point_per_value():
    points = sweep_belief("leak", [0.0, 0.2], episodes=2)
    assert [p.value for p in points] == [0.0, 0.2]
    assert all(p.episodes == 2 for p in points)


def test_a_strategy_sweep_returns_one_point_per_value():
    points = sweep_strategy("TOP_K", [1, 3], episodes=2)
    assert [p.value for p in points] == [1, 3]


def test_forbidding_every_wall_makes_a_fleeing_evader_uncatchable():
    # The headline finding of the strategy study, pinned as a regression test.
    grounded = sweep_strategy("WIDE_REACH", [0], episodes=25)[0]
    assert grounded.capture_rate == 0.0
