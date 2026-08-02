"""Shared fixtures: the real agreed config, and cheap ways to vary it.

Tests load `config/police/game.json` itself rather than a copy. The file is one
half of a signed agreement that must stay byte-identical with the thief's, so a
test fixture that drifted from it would be testing a game nobody is playing.
"""

import json
from pathlib import Path

import pytest

from police_agent.domain.scent import ScentField
from police_agent.shared.config import Config, load_config
from police_agent.shared.schema import put, translate_shared

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "police"

# The scent constants exactly as the specification fixes them (Appendix Vav,
# table 16). Spelled out rather than read from the config so that a test proving
# what a 0.9 centre looks like cannot be quietly rewritten by editing a file.
SCENT_TERMS = {
    "board_size": 7,
    "smell_grid_size": 5,
    "decay_per_step": 0.10,
    "emit_intensity": 0.9,
    "min_center_intensity": 0.5,
}


@pytest.fixture
def config() -> Config:
    """The agreed terms exactly as shipped."""
    return load_config(CONFIG_DIR)


def config_with(**overrides) -> Config:
    """The agreed terms with dotted keys overridden, e.g. `rules__max_steps=3`.

    Double underscores stand in for dots so the overrides can be keyword
    arguments; a short game is what makes a full-match test finish in
    milliseconds instead of thirty-five turns.
    """
    shared = json.loads((CONFIG_DIR / "game.json").read_text(encoding="utf-8"))
    data = translate_shared(shared)
    for key, value in overrides.items():
        put(data, key.replace("__", "."), value)
    return Config(data, shared)


def scent_field(**overrides) -> ScentField:
    """A field on the agreed constants, with any of them overridden by name."""
    return ScentField.from_terms({**SCENT_TERMS, **overrides})
