"""A resumed series must recover already-settled sub-games' summaries from
disk (team_sync/resume.py) rather than leaving `{}` placeholders -- which
would understate the final score and, under `--report`, file spurious
`unknown-group` artifacts.
"""

from police_agent.team_sync import import_adapter, scheduler
from tests.team_sync.helpers import police_summary, settled_payload
from tests.team_sync.scheduler_fakes import (
    SERIES_ID,
    FakeInboxes,
    agent_with_events,
    patch_team_sync_network,
    seed_store,
)


def test_a_resumed_run_backfills_earlier_summaries_from_disk(tmp_path, monkeypatch):
    prior_agent, _ = agent_with_events(tmp_path, num_games=4)
    prior_agent.write_artifacts(police_summary(1), tmp_path)
    imported = import_adapter.to_summary(settled_payload(2, series_id=SERIES_ID))
    prior_agent.write_artifacts(imported, tmp_path)

    inboxes = FakeInboxes()
    inboxes.subgame_results.put(settled_payload(4, series_id=SERIES_ID))
    patch_team_sync_network(monkeypatch, scheduler, inboxes)
    seed_store(tmp_path, sub_game_number=3)
    agent, events = agent_with_events(tmp_path, num_games=4)

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert [s["role"] for s in summaries] == ["police", "thief", "police", "thief"]

    game_overs = [event for event in events if event["type"] == "game_over"]
    assert game_overs[0]["totals"]["sub_games_won"]["OURTEAM"] >= 1
