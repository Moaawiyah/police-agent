"""LivePeerApp._build_title: the live window's title string.

Pure string formatting over `agent.config` and `agent.port` -- it never touches
`self._window`, so a stub carrying only `_agent` proves it without a real Tk root.
"""

from police_agent.gui.player import LivePeerApp
from tests.conftest import config_with


class FakeAgent:
    def __init__(self, config, port: int = 8801) -> None:
        self.config = config
        self.port = port


class Stub:
    """Just enough of LivePeerApp for `_build_title` to run unbound."""

    def __init__(self, config, port: int = 8801) -> None:
        self._agent = FakeAgent(config, port)


def test_title_names_the_group_the_sub_game_and_the_port():
    config = config_with(game__group_id="MOAAMOHA", game__sub_game_number=6, game__num_games=6)
    stub = Stub(config, port=8801)

    title = LivePeerApp._build_title(stub)

    assert title == "POLICE - MOAAMOHA - game 6/6 - port 8801"


def test_a_missing_sub_game_number_defaults_to_the_first_game_of_the_agreed_series():
    """No private `game.toml` override here, so sub_game_number falls back to
    1 while num_games comes from the real, agreed game.json (6)."""
    stub = Stub(config_with())

    title = LivePeerApp._build_title(stub)

    assert title == "POLICE - unnamed - game 1/6 - port 8801"


def test_an_explicit_sub_game_number_overrides_the_static_config_value():
    """`_drain` passes the series loop's own count here as each sub-game
    starts, so it must win over whatever game.toml's static value says."""
    config = config_with(game__group_id="MOAAMOHA", game__sub_game_number=1, game__num_games=6)
    stub = Stub(config, port=8801)

    title = LivePeerApp._build_title(stub, sub_game_number=4)

    assert title == "POLICE - MOAAMOHA - game 4/6 - port 8801"
