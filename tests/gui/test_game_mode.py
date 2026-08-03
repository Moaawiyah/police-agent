"""What the window says about the verbal layer, live and in replay."""

from police_agent.gui.game_mode import (
    NO_MODEL,
    OLLAMA_MODE,
    REMOTE_MODE,
    TEMPLATE_MODE,
    mode_and_model,
    mode_from_recorded_model,
)
from tests.conftest import config_with


class Settings:
    """A minimal stand-in for Config: dotted keys, nothing else."""

    def __init__(self, values: dict) -> None:
        self._values = values

    def get(self, key: str, default=None):
        return self._values.get(key, default)


def test_no_config_at_all_is_the_template_mode():
    assert mode_and_model(None) == (TEMPLATE_MODE, NO_MODEL)


def test_the_template_provider_names_no_model():
    """The window must never imply a model shaped a match that ran without one."""
    assert mode_and_model(Settings({"trash_talk.provider": "template"})) == (
        TEMPLATE_MODE,
        NO_MODEL,
    )


def test_ollama_shows_the_model_it_was_configured_with():
    settings = Settings({"trash_talk.provider": "ollama", "trash_talk.model": "llama3.1"})

    assert mode_and_model(settings) == (OLLAMA_MODE, "llama3.1")


def test_ollama_without_a_model_falls_back_to_the_shipped_default():
    assert mode_and_model(Settings({"trash_talk.provider": "ollama"})) == (OLLAMA_MODE, "qwen3:4b")


def test_an_unknown_provider_is_reported_as_a_remote_model():
    settings = Settings({"trash_talk.provider": "some_api", "llm.model": "claude-opus-4-8"})

    assert mode_and_model(settings) == (REMOTE_MODE, "claude-opus-4-8")


def test_the_shipped_test_config_reports_the_template_mode():
    """`config_with` pins the provider to `template` so no test reaches a socket."""
    assert mode_and_model(config_with()) == (TEMPLATE_MODE, NO_MODEL)


def test_a_recorded_run_with_no_model_replays_as_the_template_mode():
    for recorded in ("", "-", "none", "TEMPLATE", "  stub  "):
        assert mode_from_recorded_model(recorded) == (TEMPLATE_MODE, NO_MODEL)


def test_a_recorded_model_name_replays_under_its_own_name():
    assert mode_from_recorded_model("qwen3:4b") == (REMOTE_MODE, "qwen3:4b")
