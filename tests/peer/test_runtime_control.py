"""pump/check: turning control-channel intents into game effects."""

import pytest

from police_agent.domain.rules import ABORTED
from police_agent.exceptions import RestartRequested
from police_agent.peer import runtime_control
from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport


def runtime(**overrides) -> PoliceRuntime:
    transport = overrides.pop("transport", None) or FakeTransport()
    return PoliceRuntime(config_with(), transport, **overrides)


class TestStatusFor:
    def test_reports_quit_over_the_base_status(self):
        rt = runtime()
        rt.controls.request_quit()
        assert runtime_control._status_for(rt, runtime_control.THINKING) == runtime_control.QUIT

    def test_reports_paused_over_the_base_status(self):
        rt = runtime()
        rt.controls.pause()
        assert runtime_control._status_for(rt, runtime_control.THINKING) == "PAUSED"


class TestPump:
    def test_enables_the_link_once_requested(self):
        rt = runtime()
        rt.controls.request_enable()

        runtime_control.pump(rt, runtime_control.WAITING)

        assert rt.link.i_enabled

    def test_does_not_enable_without_a_request(self):
        rt = runtime()
        runtime_control.pump(rt, runtime_control.WAITING)
        assert not rt.link.i_enabled

    def test_broadcasts_my_status_once_enabled(self):
        transport = FakeTransport()
        rt = runtime(transport=transport)
        rt.controls.request_enable()

        runtime_control.pump(rt, runtime_control.THINKING)

        kinds = [message["kind"] for message in transport.sent_controls]
        assert "status" in kinds


class TestCheckQuit:
    def test_my_own_quit_abandons_the_sub_game_and_notifies_the_opponent(self):
        transport = FakeTransport()
        rt = runtime(transport=transport)
        rt.controls.request_quit()

        runtime_control.check(rt)

        assert rt._result == (ABORTED, None)
        assert transport.sent_controls[0]["kind"] == "quit"

    def test_the_opponents_quit_also_abandons_my_sub_game(self):
        rt = runtime()
        rt.link._opponent_quit = True

        runtime_control.check(rt)

        assert rt._result == (ABORTED, None)

    def test_nothing_requested_leaves_the_result_untouched(self):
        rt = runtime()
        runtime_control.check(rt)
        assert rt._result is None


class TestCheckRestart:
    def test_a_local_restart_request_raises_and_clears_itself(self):
        rt = runtime()
        rt.controls.request_restart()

        with pytest.raises(RestartRequested):
            runtime_control.check(rt)

        assert not rt.controls.restart_requested

    def test_a_local_restart_notifies_the_opponent(self):
        transport = FakeTransport()
        rt = runtime(transport=transport)
        rt.controls.request_restart()

        with pytest.raises(RestartRequested):
            runtime_control.check(rt)

        assert transport.sent_controls[0]["kind"] == "restart"

    def test_a_peer_approved_restart_also_raises(self):
        rt = runtime()
        rt.link._pending_restart = True

        with pytest.raises(RestartRequested):
            runtime_control.check(rt)

    def test_quit_is_checked_before_restart(self):
        """An impossible-in-practice double-request still has one right answer:
        leaving is more final than restarting, so it takes priority."""
        rt = runtime()
        rt.controls.request_quit()
        rt.controls.request_restart()

        runtime_control.check(rt)  # must not raise

        assert rt._result == (ABORTED, None)


class TestEndToEnd:
    def test_a_restart_requested_before_run_unwinds_the_whole_call_stack(self):
        """The real wiring: turn_loop pumps and checks the control channel
        before ever polling for a turn, so this never even reaches the wire."""
        transport = FakeTransport()
        rt = runtime(transport=transport)
        rt.controls.request_restart()

        with pytest.raises(RestartRequested):
            rt.run()

        assert transport.sent_turns == []
        assert transport.sent_controls[0]["kind"] == "restart"

    def test_a_quit_requested_before_run_ends_the_match_without_raising(self):
        """The other branch of the same wiring: check() can also settle the
        result directly (no exception), and turn_loop must return at once
        rather than falling through to poll_turn."""
        transport = FakeTransport()
        rt = runtime(transport=transport)
        rt.controls.request_quit()

        summary = rt.run()

        assert summary["result"] == ABORTED
        assert transport.sent_turns == []
