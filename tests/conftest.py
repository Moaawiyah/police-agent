"""Shared fixtures: the real agreed config, and cheap ways to vary it.

Tests load `config/police/game.json` itself rather than a copy. The file is one
half of a signed agreement that must stay byte-identical with the thief's, so a
test fixture that drifted from it would be testing a game nobody is playing.
"""

import json
from pathlib import Path

import pytest

from police_agent.shared.config import Config, load_config
from police_agent.shared.schema import put, translate_shared

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "police"


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
