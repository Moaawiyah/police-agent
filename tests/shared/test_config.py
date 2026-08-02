"""Config loading: the agreed file wins, and a missing one is loud."""

import pytest

from police_agent.exceptions import ConfigError
from police_agent.shared.config import Config, load_config
from police_agent.shared.schema import dig, put, translate_shared

SHARED = {
    "board_and_agents": {"grid_size": 9, "cop_start": [0, 0], "thief_start": [4, 4]},
    "movement_and_barriers": {"max_barriers": 3, "max_moves": 20, "survival_threshold": 20},
    "scoring": {"capture_cop": 20},
}


def test_the_shipped_config_loads_and_carries_the_agreed_terms(config):
    assert config.get("board.size") == 7
    assert config.get("positions.cop_start") == [0, 0]
    assert config.get("rules.barriers_max") == 14
    assert config.get("rules.max_steps") == 35


def test_the_raw_agreed_file_is_kept_for_signing(config):
    """The signature is over the agreed terms, so the original must survive loading."""
    assert config.shared["board_and_agents"]["grid_size"] == 7


def test_a_missing_directory_is_reported_by_name(tmp_path):
    with pytest.raises(ConfigError, match="Config directory not found"):
        load_config(tmp_path / "nowhere")


def test_a_missing_agreed_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="Missing config file"):
        load_config(tmp_path)


def test_malformed_json_is_reported_as_config_not_as_a_crash(tmp_path):
    (tmp_path / "game.json").write_text("{ not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_config(tmp_path)


def test_malformed_toml_is_reported(tmp_path):
    (tmp_path / "game.json").write_text("{}", encoding="utf-8")
    (tmp_path / "game.toml").write_text("this is not = = toml", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(tmp_path)


def test_the_private_file_supplies_settings_the_agreed_one_does_not(tmp_path):
    (tmp_path / "game.json").write_text("{}", encoding="utf-8")
    (tmp_path / "game.toml").write_text(
        '[network]\nmy_port = 8801\nopponent_url = "http://x/mcp"\n', encoding="utf-8"
    )

    loaded = load_config(tmp_path)

    assert loaded.get("network.my_port") == 8801
    assert loaded.get("network.opponent_url") == "http://x/mcp"


def test_the_private_file_cannot_override_an_agreed_term(tmp_path):
    """A peer must not be able to sign one board size and play another."""
    (tmp_path / "game.json").write_text('{"board_and_agents": {"grid_size": 7}}', encoding="utf-8")
    (tmp_path / "game.toml").write_text("[board]\nsize = 99\n", encoding="utf-8")

    assert load_config(tmp_path).get("board.size") == 7


def test_require_names_the_key_it_could_not_find():
    with pytest.raises(ConfigError, match="network.opponent_url"):
        Config({}).require("network.opponent_url")


def test_get_falls_back_when_a_key_or_its_section_is_absent():
    assert Config({}).get("network.my_port", 8801) == 8801
    assert Config({"network": "not-a-section"}).get("network.my_port") is None


def test_translation_emits_only_the_keys_the_agreed_file_actually_has():
    translated = translate_shared(SHARED)

    assert translated["board"]["size"] == 9
    assert translated["rules"]["barriers_max"] == 3
    assert translated["scoring"] == {"capture_cop": 20}
    assert "smell" not in translated  # no pheromones block was supplied


def test_put_and_dig_round_trip_a_nested_key():
    target: dict = {}
    put(target, "a.b.c", 1)

    assert target == {"a": {"b": {"c": 1}}}
    assert dig(target, "a.b.c") == 1
    assert dig(target, "a.b.missing", "fallback") == "fallback"
