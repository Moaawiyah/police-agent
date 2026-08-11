"""LivePeerApp's window title: group and port only.

The sub-game number used to live here too; it now lives on the "Sub-game"
panel row instead (see `tests/gui/test_live_apply.py`), so the header stays
stable across the whole series and a screenshot of it never goes stale.
"""

from unittest.mock import patch

from police_agent.gui.player import LivePeerApp
from police_agent.peer.controls import GameControls
from tests.conftest import config_with


def _title(config, port: int = 8801) -> str:
    agent = type("FakeAgent", (), {"config": config, "port": port, "listener": None})()
    with (
        patch("police_agent.gui.player.PeerWindow"),
        patch.object(LivePeerApp, "_describe_verbal_layer"),
        patch("police_agent.gui.player.LiveControls"),
    ):
        app = LivePeerApp(agent, controls=GameControls())
    return app._title


def test_title_names_the_group_and_the_port():
    config = config_with(game__group_id="MOAAMOHA")

    assert _title(config, port=8801) == "POLICE - MOAAMOHA - port 8801"


def test_title_does_not_mention_the_sub_game_number():
    """That number changes every sub-game; the title must not, or the OS
    window list would relabel itself mid-series for no reason a user asked for."""
    config = config_with(game__group_id="MOAAMOHA", game__sub_game_number=6, game__num_games=6)

    assert "game" not in _title(config).lower().split(" - ")[0]
    assert "6" not in _title(config)
