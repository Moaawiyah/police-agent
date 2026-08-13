"""Test doubles and fixtures for `test_scheduler.py`, split out to keep that
file within the project's line budget: a fake coordinator inbox pair, a fake
sibling client that records calls instead of touching a socket, and the
small agent/store scaffolding every scheduler test needs.
"""

import queue

from police_agent.exceptions import TransportError
from police_agent.sdk import PoliceAgentSDK
from police_agent.team_sync.state import SeriesSyncState, SeriesSyncStatus
from police_agent.team_sync.store import TeamSyncStore
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport, thief_turn

SERIES_ID = "series-1"


class FakeInboxes:
    """Mirrors `coordinator.CoordinatorInboxes`, pre-loadable by a test."""

    def __init__(self) -> None:
        self.subgame_results: queue.Queue = queue.Queue()
        self.acks: queue.Queue = queue.Queue()


class FakeSiblingClient:
    """Records every outbound call instead of touching a socket.

    `instances` collects every constructed client -- `scheduler.py` builds
    exactly one per `run_team_series` call, so a test can inspect what the
    *last* run sent without scheduler.py handing the instance back itself.
    """

    instances: list = []
    fail_on: set = set()  # tool names that should raise TransportError, set by a test

    def __init__(self, sibling_url: str, secret, **_kwargs) -> None:
        self.calls: list = []
        FakeSiblingClient.instances.append(self)

    def _maybe_fail(self, tool: str) -> None:
        if tool in FakeSiblingClient.fail_on:
            raise TransportError(f"fake sibling unreachable for {tool!r}")

    def send_series_start(self, series_id, group_id, total, first_sibling_subgame):
        self.calls.append(("series_start", series_id, group_id, total, first_sibling_subgame))
        self._maybe_fail("series_start")
        return {"ok": True}

    def send_handoff(self, series_id, completed, next_subgame):
        self.calls.append(("handoff", series_id, completed, next_subgame))
        self._maybe_fail("handoff")
        return {"ok": True}

    def send_status_request(self, series_id):
        self.calls.append(("status_request", series_id))
        return {}

    def send_ack(self, series_id, ack_for_message_id, sub_game_number):
        self.calls.append(("ack", series_id, ack_for_message_id, sub_game_number))
        return {"ok": True}


def agent_with_events(tmp_path, incoming=None, num_games=2):
    """A real `PoliceAgentSDK` over a `FakeTransport`, plus a listener spy."""
    config = config_with(game__group_id="OURTEAM", game__num_games=num_games, rules__max_steps=1)
    transport = FakeTransport(incoming=incoming or [thief_turn(1)])
    agent = PoliceAgentSDK(config=config, transport=transport)
    agent.email_report = lambda paths: "stubbed"
    events: list = []
    agent.listener = events.append
    return agent, events


def patch_team_sync_network(monkeypatch, scheduler, inboxes: FakeInboxes):
    """Replace the coordinator and sibling client with in-process fakes."""
    monkeypatch.setattr(
        scheduler.ts_coordinator,
        "start_coordinator",
        lambda host, port, secret, provider: (inboxes, None),
    )
    monkeypatch.setattr(scheduler.ts_client, "TeamSyncClient", FakeSiblingClient)


def seed_store(tmp_path, sub_game_number=1):
    """Pre-file a `SeriesSyncStatus` so a test controls the series id and position."""
    store = TeamSyncStore(tmp_path / "OURTEAM" / "team_sync")
    store.save_status(
        SeriesSyncStatus(
            series_id=SERIES_ID, sub_game_number=sub_game_number, state=SeriesSyncState.READY
        )
    )
    return store
