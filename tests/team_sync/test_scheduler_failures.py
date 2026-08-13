"""A stuck or unreachable sibling must leave a visible trace: a persisted
ERROR status and a listener event, never a bare uncaught traceback -- and
never a silent hang either."""

import pytest

from police_agent.exceptions import TransportError
from police_agent.team_sync import scheduler
from police_agent.team_sync.state import SeriesSyncState, SeriesSyncStatus
from police_agent.team_sync.store import TeamSyncStore
from tests.team_sync.scheduler_fakes import (
    SERIES_ID,
    FakeInboxes,
    FakeSiblingClient,
    agent_with_events,
    patch_team_sync_network,
    seed_store,
)


@pytest.fixture(autouse=True)
def _reset_fake_client():
    FakeSiblingClient.fail_on = set()
    yield
    FakeSiblingClient.fail_on = set()


def test_an_unreachable_sibling_at_series_start_persists_error_and_raises(tmp_path, monkeypatch):
    FakeSiblingClient.fail_on = {"series_start"}
    inboxes = FakeInboxes()
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, events = agent_with_events(tmp_path)

    with pytest.raises(TransportError, match="announce the series"):
        scheduler.run_team_series(agent, base=tmp_path)

    store = TeamSyncStore(tmp_path / "OURTEAM" / "team_sync")
    assert store.load_status().state == SeriesSyncState.ERROR
    assert any(e.get("status", "").startswith("ERROR") for e in events)


def test_an_unreachable_sibling_at_handoff_persists_error_and_raises(tmp_path, monkeypatch):
    FakeSiblingClient.fail_on = {"handoff"}
    inboxes = FakeInboxes()
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, events = agent_with_events(tmp_path)

    with pytest.raises(TransportError, match="handoff to Thief failed"):
        scheduler.run_team_series(agent, base=tmp_path)

    store = TeamSyncStore(tmp_path / "OURTEAM" / "team_sync")
    assert store.load_status().state == SeriesSyncState.ERROR
    assert any(e.get("status", "").startswith("ERROR") for e in events)


def test_a_timed_out_wait_for_thief_persists_error_and_raises(tmp_path, monkeypatch):
    inboxes = FakeInboxes()  # left empty: the wait times out
    monkeypatch.setattr(scheduler, "wait_for_thief_result", _raise_transport_error)
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, events = agent_with_events(tmp_path)

    with pytest.raises(TransportError, match="no thief"):
        scheduler.run_team_series(agent, base=tmp_path)

    store = TeamSyncStore(tmp_path / "OURTEAM" / "team_sync")
    assert store.load_status().state == SeriesSyncState.ERROR
    assert any(e.get("status", "").startswith("ERROR") for e in events)


def _raise_transport_error(inboxes, series_id, sub_game_number):
    raise TransportError("no thief result arrived")


def test_fail_is_a_legal_transition_from_ready_and_waiting_for_sibling(tmp_path):
    """The two states `run_team_series` can be in when a sibling call fails --
    guards against the state machine silently rejecting the ERROR move."""
    from police_agent.team_sync.scheduler_fail import fail

    store = TeamSyncStore(tmp_path / "team_sync")
    ready = SeriesSyncStatus(series_id=SERIES_ID).advance(SeriesSyncState.READY)
    waiting = ready.advance(SeriesSyncState.WAITING_FOR_SIBLING)

    for status in (ready, waiting):
        with pytest.raises(TransportError):
            fail(_agent_without_listener(), store, status, "boom")
        assert store.load_status().state == SeriesSyncState.ERROR


def _agent_without_listener():
    class _Agent:
        listener = None

    return _Agent()
