"""restart / toggle_bidirectional / rebuild_and_start against a stub app --
no Tk root needed, matching how live_apply.py is tested against FakeWindow.
"""

from police_agent.gui import live_restart
from police_agent.peer.controls import GameControls
from tests.gui.fake_window import FakeWindow


class FakeAgent:
    def __init__(self) -> None:
        self.restart_calls = 0
        self.controls = None

    def restart(self) -> None:
        self.restart_calls += 1


class FakeVar:
    def __init__(self, value: bool = False) -> None:
        self._value = value

    def get(self) -> bool:
        return self._value


class FakeBar:
    def __init__(self, bidi: bool = False) -> None:
        self.bidi_var = FakeVar(bidi)


class FakeApp:
    """Just enough of LivePeerApp for live_restart's functions to operate on."""

    def __init__(self, in_progress: bool = False, bidi: bool = False) -> None:
        self._in_progress = in_progress
        self._controls = GameControls()
        self._agent = FakeAgent()
        self._window = FakeWindow()
        self._bar = FakeBar(bidi)
        self._summaries = [{"result": "stale"}]
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1


class TestRestart:
    def test_mid_game_requests_through_the_control_channel_rather_than_rebuilding(self):
        app = FakeApp(in_progress=True)

        live_restart.restart(app)

        assert app._controls.restart_requested
        assert app._agent.restart_calls == 0
        assert app.start_calls == 0
        assert app._window.labels["status"] == "restart requested..."

    def test_post_game_rebuilds_directly(self):
        app = FakeApp(in_progress=False)

        live_restart.restart(app)

        assert app._agent.restart_calls == 1
        assert app.start_calls == 1


class TestToggleBidirectional:
    def test_requests_enable_on_the_current_controls(self):
        app = FakeApp()
        live_restart.toggle_bidirectional(app)
        assert app._controls.enable_requested


class TestRebuildAndStart:
    def test_drops_in_progress_and_the_stale_summary(self):
        app = FakeApp(in_progress=True)
        live_restart.rebuild_and_start(app)
        assert not app._in_progress
        assert app._summaries == []

    def test_builds_fresh_controls_and_rewires_the_agent(self):
        app = FakeApp(in_progress=True)
        old_controls = app._controls

        live_restart.rebuild_and_start(app)

        assert app._controls is not old_controls
        assert app._agent.controls is app._controls

    def test_calls_agent_restart_and_then_start(self):
        app = FakeApp()
        live_restart.rebuild_and_start(app)
        assert app._agent.restart_calls == 1
        assert app.start_calls == 1

    def test_carries_a_checked_bidirectional_box_into_the_fresh_controls(self):
        """Without this, restarting would silently uncheck the box's real
        effect even though it still looks ticked in the window."""
        app = FakeApp(bidi=True)
        live_restart.rebuild_and_start(app)
        assert app._controls.enable_requested

    def test_an_unchecked_box_stays_unrequested(self):
        app = FakeApp(bidi=False)
        live_restart.rebuild_and_start(app)
        assert not app._controls.enable_requested
