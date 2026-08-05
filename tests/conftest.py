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

# What the probes answer in the suite. Every runtime now seals a step-zero
# declaration, so without this the whole suite would shell out to sysctl and git
# and a test's result could depend on which machine ran it.
STUB_SPEC = {
    "os": "TestOS 1.0",
    "cpu_type": "Test CPU",
    "cpu_cores": 4,
    "cpu_freq_mhz": 2400,
    "ram_gb": 16.0,
    "gpu_type": "Test GPU",
    "gpu_cores_or_cuda": 8,
    "vram_gb": 4.0,
}
STUB_COMMIT = "0" * 40

# Patched at the point of *use*, not at the source module: both consumers
# `from`-import these names, which binds them at import time, so replacing the
# attribute on `infra.hardware` would never reach them.
_PROBE_CONSUMERS = ("police_agent.peer.step_zero", "police_agent.peer.handshake")


@pytest.fixture(autouse=True)
def _stub_machine_probes(monkeypatch):
    """Pin the machine and the commit for every test that seals a declaration.

    Every runtime now builds a step-zero record, so without this the suite would
    shell out to sysctl, system_profiler and git on each construction -- slow,
    and it would make a test's result depend on which machine ran it.

    `tests/infra/test_hardware.py` and `test_gitcommit.py` are unaffected: they
    import the real functions directly and install their own subprocess fakes,
    which is exactly what a test *about* the probes should do.
    """
    for module in _PROBE_CONSUMERS:
        monkeypatch.setattr(f"{module}.hardware_spec", lambda: dict(STUB_SPEC), raising=False)
        monkeypatch.setattr(f"{module}.commit_hash", lambda config=None: STUB_COMMIT, raising=False)
        monkeypatch.setattr(f"{module}.working_tree_dirty", lambda: False, raising=False)


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
    # The shipped agent asks a local model for its banter. A unit test must not:
    # it would reach for a socket every turn, pass or fail on whether Ollama
    # happens to be running, and take seconds doing it. Tests that want the model
    # path inject their own asker (see tests/strategy/test_talk.py).
    put(data, "trash_talk.provider", "template")
    for key, value in overrides.items():
        put(data, key.replace("__", "."), value)
    return Config(data, shared)


def scent_field(**overrides) -> ScentField:
    """A field on the agreed constants, with any of them overridden by name."""
    return ScentField.from_terms({**SCENT_TERMS, **overrides})
