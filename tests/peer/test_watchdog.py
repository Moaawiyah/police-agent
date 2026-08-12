"""The loop-liveness monitor: beats keep it quiet, silence trips it."""

import threading
import time

from police_agent.peer.controls import GameControls
from police_agent.peer.watchdog import Watchdog
from tests.conftest import config_with


def test_beat_keeps_the_watchdog_from_tripping():
    controls = GameControls()
    watchdog = Watchdog(controls, timeout_sec=0.3, poll_sec=0.05)
    watchdog.start()
    try:
        for _ in range(6):
            time.sleep(0.08)
            watchdog.beat()
    finally:
        watchdog.stop()

    assert not watchdog.tripped
    assert not controls.stopped


def test_no_heartbeat_trips_and_stops_the_controls():
    controls = GameControls()
    tripped_event = threading.Event()
    watchdog = Watchdog(
        controls, timeout_sec=0.1, poll_sec=0.03, on_trip=lambda reason: tripped_event.set()
    )

    watchdog.start()
    try:
        assert tripped_event.wait(timeout=2.0)
    finally:
        watchdog.stop()

    assert watchdog.tripped
    assert controls.stopped


def test_the_trip_reason_names_the_watchdog_and_the_elapsed_time():
    controls = GameControls()
    tripped_event = threading.Event()
    reasons: list[str] = []

    def on_trip(reason: str) -> None:
        reasons.append(reason)
        tripped_event.set()

    watchdog = Watchdog(controls, timeout_sec=0.1, poll_sec=0.03, on_trip=on_trip)

    watchdog.start()
    try:
        assert tripped_event.wait(timeout=2.0)
    finally:
        watchdog.stop()

    assert "watchdog" in reasons[0]
    assert "limit" in reasons[0]


def test_a_pause_does_not_trip_the_watchdog():
    controls = GameControls()
    controls.pause()
    watchdog = Watchdog(controls, timeout_sec=0.1, poll_sec=0.03)

    watchdog.start()
    try:
        time.sleep(0.3)
    finally:
        watchdog.stop()

    assert not watchdog.tripped
    assert not controls.stopped


def test_unpausing_resumes_the_countdown():
    controls = GameControls()
    controls.pause()
    tripped_event = threading.Event()
    watchdog = Watchdog(
        controls, timeout_sec=0.1, poll_sec=0.03, on_trip=lambda reason: tripped_event.set()
    )

    watchdog.start()
    try:
        time.sleep(0.3)
        assert not tripped_event.is_set()
        controls.play()
        assert tripped_event.wait(timeout=2.0)
    finally:
        watchdog.stop()


def test_stop_joins_the_monitor_thread():
    controls = GameControls()
    watchdog = Watchdog(controls, timeout_sec=5.0, poll_sec=0.05)

    watchdog.start()
    watchdog.stop()

    assert not watchdog._thread.is_alive()


def test_from_config_reads_the_dedicated_key():
    controls = GameControls()
    config = config_with(reliability__loop_watchdog_timeout_seconds=42.0)

    watchdog = Watchdog.from_config(config, controls)

    assert watchdog.timeout_sec == 42.0
