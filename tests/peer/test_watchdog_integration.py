"""The watchdog wired end to end through PoliceRuntime, not just in isolation."""

import time

from police_agent.domain.rules import ABORTED
from police_agent.peer.controls import GameControls
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.watchdog import Watchdog
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turns


def test_an_ordinary_match_never_trips_the_watchdog():
    runtime = PoliceRuntime(config_with(), FakeTransport(incoming=thief_turns(3)))

    summary = runtime.run()

    assert summary["abort_reason"] is None
    assert runtime.watchdog.tripped is False


def test_a_wedged_turn_step_is_recovered_by_the_watchdog():
    """Simulates exactly the realistic hang this feature targets: an
    unbounded call somewhere inside apply_incoming (here, TurnHandler.process
    itself), outside any of poll_turn's own bounded wait."""
    config = config_with()
    transport = FakeTransport(incoming=thief_turns(3))
    controls = GameControls()
    watchdog = Watchdog(controls, timeout_sec=0.05, poll_sec=0.02)
    runtime = PoliceRuntime(config, transport, controls=controls, watchdog=watchdog)
    # PeerRuntime normally wires this itself via Watchdog.from_config when it
    # builds its own watchdog; done by hand here since this test supplies a
    # pre-built one (to control poll_sec, which from_config doesn't expose).
    watchdog._on_trip = runtime._set_abort_reason

    original_process = runtime.handler.process

    def slow_process(message):
        time.sleep(0.3)
        return original_process(message)

    runtime.handler.process = slow_process

    summary = runtime.run()

    assert summary["result"] == ABORTED
    assert "watchdog" in summary["abort_reason"]
