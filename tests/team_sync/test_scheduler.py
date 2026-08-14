"""The orchestration loop: alternates Police's own sub-games with imported
Thief ones, over a faked coordinator/client so no real socket is opened.
"""

from police_agent.team_sync import scheduler
from tests.team_sync.helpers import settled_payload
from tests.team_sync.scheduler_fakes import (
    SERIES_ID,
    FakeInboxes,
    FakeSiblingClient,
    agent_with_events,
    patch_team_sync_network,
    seed_store,
)


def test_a_two_subgame_series_plays_one_and_imports_the_other(tmp_path, monkeypatch):
    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, _ = agent_with_events(tmp_path)

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert len(summaries) == 2
    assert summaries[0]["role"] == "police"  # sub-game 1: played directly
    assert summaries[1]["role"] == "thief"  # sub-game 2: imported


def test_the_series_start_and_handoff_are_sent_to_the_sibling(tmp_path, monkeypatch):
    """No separate `ack` round-trip: the sibling's `subgame_result` tool call
    already returns `{"ok": True}` synchronously (see `scheduler.py`)."""
    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, _ = agent_with_events(tmp_path)
    FakeSiblingClient.instances.clear()

    scheduler.run_team_series(agent, base=tmp_path)

    kinds = [call[0] for call in FakeSiblingClient.instances[-1].calls]
    assert kinds == ["series_start", "handoff"]
    assert FakeSiblingClient.instances[-1].calls[0][-1] == 1  # sibling also joins G1


def test_a_message_for_the_wrong_series_id_is_rejected(tmp_path, monkeypatch):
    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(2, series_id="a-different-series"))
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, _ = agent_with_events(tmp_path)

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert summaries[1]["result"] == "capture"  # the second (correct) message was used


def test_a_message_for_the_wrong_subgame_number_is_rejected(tmp_path, monkeypatch):
    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(6, series_id=SERIES_ID))  # out of order
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, _ = agent_with_events(tmp_path)

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert summaries[1]["step_zero"]["sub_game_number"] == 2


def test_a_message_from_the_wrong_sender_role_is_rejected(tmp_path, monkeypatch):
    inboxes = FakeInboxes()
    impostor = settled_payload(2, series_id=SERIES_ID)
    impostor["sender_role"] = "police"
    inboxes.subgame_results.put(impostor)
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, _ = agent_with_events(tmp_path)

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert summaries[1]["role"] == "thief"


def test_resuming_from_subgame_two_does_not_replay_subgame_one(tmp_path, monkeypatch):
    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path, sub_game_number=2)  # as if sub-game 1 already settled and persisted
    agent, _ = agent_with_events(tmp_path)

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert summaries[0] == {}  # never touched this run
    assert summaries[1]["role"] == "thief"


def test_the_final_game_over_event_carries_series_totals(tmp_path, monkeypatch):
    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(2, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path)
    agent, events = agent_with_events(tmp_path)

    scheduler.run_team_series(agent, base=tmp_path)

    game_overs = [event for event in events if event["type"] == "game_over"]
    assert len(game_overs) == 1
    assert "totals" in game_overs[0]
