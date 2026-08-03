"""The pause/stop switches, and the turn loop actually honouring them."""

import threading

from police_agent.domain.rules import ABORTED
from police_agent.peer.controls import GameControls
from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn


def test_controls_start_running():
    controls = GameControls()

    assert not controls.paused
    assert not controls.stopped


def test_pause_and_play_toggle_the_switch():
    controls = GameControls()

    controls.pause()
    assert controls.paused

    controls.play()
    assert not controls.paused


def test_wait_returns_at_once_when_not_paused():
    GameControls().wait_if_paused()  # would hang if it did not


def test_stopping_releases_a_paused_waiter():
    """Otherwise a runtime paused from the GUI could never notice the Stop that
    followed it, and the window's own button would deadlock the game."""
    controls = GameControls()
    controls.pause()
    released = threading.Event()

    def wait() -> None:
        controls.wait_if_paused()
        released.set()

    threading.Thread(target=wait, daemon=True).start()
    controls.stop()

    assert released.wait(timeout=2.0)
    assert controls.stopped


def test_a_pause_pressed_after_a_stop_does_not_hold_the_runtime():
    """A real sequence: the buttons stay live until the game-over event drains.
    Waiting first would block on an event nothing was going to set again."""
    controls = GameControls()
    controls.stop()
    controls.pause()

    controls.wait_if_paused()  # would hang if the stop were checked after the wait


def test_a_stopped_runtime_abandons_the_sub_game():
    controls = GameControls()
    controls.stop()
    transport = FakeTransport(incoming=[thief_turn(1)])

    summary = PoliceRuntime(config_with(), transport, controls=controls).run()

    assert summary["result"] == ABORTED
    assert transport.sent_turns == []  # stopped before it answered anything


def test_an_abandoned_game_does_not_ask_the_opponent_to_reveal():
    """We are the peer that walked away. Demanding an audit would only stall
    this one for a full reply timeout against a thief still playing."""
    controls = GameControls()
    controls.stop()
    transport = FakeTransport(incoming=[thief_turn(1)])

    summary = PoliceRuntime(config_with(), transport, controls=controls).run()

    assert transport.sent_audits == []
    assert summary["audit"]["skipped"] is True
