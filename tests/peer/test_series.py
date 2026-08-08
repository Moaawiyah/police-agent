"""run_series: playing the whole agreed series over one held connection."""

import pytest

from police_agent.exceptions import ConfigError
from police_agent.peer.controls import GameControls
from police_agent.peer.series import run_series, series_count
from police_agent.shared.config import Config
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn


class TestSeriesCount:
    def test_reads_the_agreed_number_of_games(self):
        assert series_count(config_with(game__num_games=4)) == 4

    def test_defaults_to_one_when_absent(self):
        assert series_count(Config({})) == 1

    @pytest.mark.parametrize("bad", [0, 7, -1, True, "6", 3.0])
    def test_refuses_anything_outside_one_through_six(self, bad):
        with pytest.raises(ConfigError, match="1 through 6"):
            series_count(config_with(game__num_games=bad))


class TestRunSeries:
    def test_plays_exactly_the_agreed_number_of_sub_games(self):
        # An empty script is a silent opponent: each sub-game ends at once
        # (technical loss), which is all this needs to prove the loop ran.
        transport = FakeTransport(incoming=[])
        summaries = run_series(config_with(game__num_games=3), transport)

        assert len(summaries) == 3

    def test_each_sub_game_declares_its_own_number(self):
        transport = FakeTransport(incoming=[])
        summaries = run_series(config_with(game__num_games=3), transport)

        declared = [s["step_zero"]["sub_game_number"] for s in summaries]
        assert declared == [1, 2, 3]

    def test_the_same_transport_carries_every_sub_game(self):
        """One held connection, not one per sub-game: a survival claim ends
        its sub-game the instant it is decided (no further polling), and
        reaching a decided result -- unlike a technical loss -- means an
        end-of-game audit exchange too. All three land on the one
        `transport` passed in, never a fresh one."""
        script = [thief_turn(1, win_claim={"type": "survival"}) for _ in range(3)]
        transport = FakeTransport(incoming=script)
        run_series(config_with(game__num_games=3, rules__survival_threshold=1), transport)

        assert len(transport.sent_audits) == 3

    def test_controls_persist_across_sub_games_rather_than_resetting(self):
        """A stop set before the series starts must abandon every sub-game,
        not just the first -- proof the same GameControls is reused, not
        rebuilt fresh each iteration."""
        controls = GameControls()
        controls.stop()
        transport = FakeTransport(incoming=[thief_turn(1)])

        summaries = run_series(config_with(game__num_games=3), transport, controls=controls)

        assert all(s["result"] == "aborted" for s in summaries)

    def test_a_default_controls_object_is_built_when_none_is_given(self):
        transport = FakeTransport(incoming=[])
        summaries = run_series(config_with(game__num_games=1), transport)

        assert summaries[0]["result"] == "technical_loss"
