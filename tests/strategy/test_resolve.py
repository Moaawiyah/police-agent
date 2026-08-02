"""Tests for the config-selectable brain factory.

The dotted selectors below name this very module. Under pytest's default import
mode the test packages carry `__init__.py`, so the project root is on `sys.path`
and this file is importable as `tests.strategy.test_resolve` -- exactly the kind
of dotted path a submitted config would carry.
"""

import random

import pytest

from police_agent.domain.own_state import OwnGameState
from police_agent.strategy import (
    PoliceBrain,
    PoliceBrainBase,
    load_brain_cls,
    resolve_brain,
    resolve_brain_cls,
)
from police_agent.strategy.threat import PointThreat

MODULE = "tests.strategy.test_resolve"
DOTTED = f"{MODULE}:StubbornBrain"


class StubbornBrain(PoliceBrainBase):
    """A replacement policy: always take the first legal step, ignoring the belief."""

    def _pick_move(self, moves, state, threat):
        return moves[0]


class NotABrain:
    """A perfectly good class that is not a brain -- the selector must reject it."""


class TestDefaults:
    def test_no_config_at_all_gives_the_shipped_brain(self):
        assert resolve_brain_cls(None) is PoliceBrain
        assert type(resolve_brain(None)) is PoliceBrain

    def test_an_empty_config_gives_the_shipped_brain(self):
        assert resolve_brain_cls({}) is PoliceBrain

    def test_an_unrelated_config_gives_the_shipped_brain(self):
        assert resolve_brain_cls({"network.my_port": 8801}) is PoliceBrain

    def test_the_rng_is_handed_to_the_brain(self):
        rng = random.Random(7)
        assert resolve_brain(None, rng=rng)._rng is rng

    def test_an_omitted_rng_still_produces_a_usable_brain(self):
        brain = resolve_brain()
        assert brain._rng is not None
        assert brain.decide(_state(), PointThreat((0, 0))).action is not None


class TestSelector:
    def test_a_flattened_dotted_key_selects_the_class(self):
        config = {"strategy.police_class": DOTTED}
        assert resolve_brain_cls(config) is StubbornBrain
        assert isinstance(resolve_brain(config), StubbornBrain)

    def test_a_nested_toml_table_selects_the_class_too(self):
        # Raw `tomllib` output keeps [strategy] as a nested table.
        assert resolve_brain_cls({"strategy": {"police_class": DOTTED}}) is StubbornBrain

    def test_a_nested_table_without_the_key_falls_back(self):
        assert resolve_brain_cls({"strategy": {"something_else": 1}}) is PoliceBrain

    def test_a_non_mapping_strategy_value_falls_back(self):
        assert resolve_brain_cls({"strategy": "not-a-table"}) is PoliceBrain

    def test_the_selected_brain_actually_drives_the_move(self):
        state, threat = _state(), PointThreat((4, 4))
        chosen = resolve_brain({"strategy.police_class": DOTTED}).decide(state, threat)
        shipped = PoliceBrain().decide(state, threat)
        assert chosen.action != shipped.action


class TestSelectorFailures:
    """A typo must fail loudly: a game silently played with the wrong brain is worse."""

    @pytest.mark.parametrize("bad", ["no_colon_here", "module:", ":ClassName", ""])
    def test_a_malformed_selector_raises(self, bad):
        with pytest.raises(ValueError, match="package.module:ClassName"):
            load_brain_cls(bad)

    def test_a_missing_attribute_raises(self):
        with pytest.raises(ValueError, match="not found in module"):
            load_brain_cls(f"{MODULE}:NoSuchBrain")

    def test_an_unimportable_module_raises(self):
        with pytest.raises(ModuleNotFoundError):
            load_brain_cls("no.such.module:PoliceBrain")

    def test_a_class_that_is_not_a_brain_raises(self):
        with pytest.raises(TypeError, match="PoliceBrainBase subclass"):
            load_brain_cls(f"{MODULE}:NotABrain")

    def test_a_non_class_target_raises(self):
        with pytest.raises(TypeError, match="PoliceBrainBase subclass"):
            load_brain_cls(f"{MODULE}:MODULE")


def _state():
    return OwnGameState(start=(2, 2), board_size=5)
