"""PoliceAgentSDK.play_series: playing the whole agreed series through the SDK.

Split from test_agent_lifecycle.py (single-game play) to keep both files
under the project's 150-line rule.
"""

from tests.peer.fake_transport import FakeTransport
from tests.sdk.conftest import agent_with


def test_play_series_returns_one_summary_per_sub_game():
    # An empty script is a silent opponent: each sub-game ends at once.
    agent = agent_with(game__num_games=2, transport=FakeTransport(incoming=[]))

    summaries = agent.play_series()

    assert len(summaries) == 2


def test_play_series_reuses_the_one_connection_the_sdk_already_opened():
    transport = FakeTransport(incoming=[])
    agent = agent_with(game__num_games=3, transport=transport)

    agent.play_series()

    assert agent.connect() is transport


def test_only_the_last_sub_game_is_reported_as_game_over():
    """`game_over` means "the whole series just ended" for anything watching
    the listener (the live GUI treats it as the point to stop) -- the first
    two sub-games must not be mistaken for that."""
    events: list[dict] = []
    agent = agent_with(
        game__num_games=3, transport=FakeTransport(incoming=[]), listener=events.append
    )

    agent.play_series()

    kinds = [event["type"] for event in events]
    assert kinds.count("game_over") == 1
    assert kinds.count("sub_game_over") == 3  # every sub-game, including the last
    assert kinds[-1] == "game_over"  # but the series-ending signal only ever fires once


def test_the_final_game_over_names_every_sub_game_played():
    events: list[dict] = []
    agent = agent_with(
        game__num_games=3, transport=FakeTransport(incoming=[]), listener=events.append
    )

    summaries = agent.play_series()

    final = events[-1]
    assert final["summaries"] == summaries
    assert final["sub_game_number"] == 3


def test_no_listener_is_a_quiet_series():
    """No listener was given, so `play_series` must not crash reaching for one
    when the last sub-game ends."""
    agent = agent_with(game__num_games=2, transport=FakeTransport(incoming=[]))

    summaries = agent.play_series()

    assert len(summaries) == 2
