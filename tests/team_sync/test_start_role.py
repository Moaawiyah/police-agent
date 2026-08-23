"""Series synchronization tests for both opening-role schedules."""

import queue
from types import SimpleNamespace

import pytest

from police_agent.team_sync import scheduler
from police_agent.team_sync.messages import SubgameHandoff
from police_agent.team_sync.state import role_for_subgame
from tests.team_sync.helpers import police_summary, settled_payload
from tests.team_sync.scheduler_fakes import FakeSiblingClient, agent_with_events


@pytest.mark.parametrize(
    ("start_role", "expected"),
    [
        ("police", ["police", "thief", "police", "thief", "police", "thief"]),
        ("thief", ["thief", "police", "thief", "police", "thief", "police"]),
    ],
)
def test_role_for_subgame_matches_both_schedules(start_role, expected):
    assert [role_for_subgame(n, start_role) for n in range(1, 7)] == expected


def test_handoff_carries_settlement_and_next_role_metadata():
    message = SubgameHandoff(
        series_id="s1",
        completed_subgame=1,
        next_subgame=2,
        sub_game_number=2,
        sender_role="police",
        start_role="thief",
        next_role="police",
    ).to_dict()
    assert message["status"] == "settled"
    assert message["start_role"] == "thief"
    assert message["next_role"] == "police"


def test_police_accepts_thief_started_series_and_emails_once_after_all_six(tmp_path, monkeypatch):
    class Inboxes:
        def __init__(self):
            self.series_start = queue.Queue()
            self.subgame_results = queue.Queue()
            self.acks = queue.Queue()

    inboxes = Inboxes()
    inboxes.series_start.put(
        {
            "series_id": "series-1",
            "sender_role": "thief",
            "start_role": "thief",
            "next_role": "thief",
            "sub_game_number": 1,
        }
    )
    for n in (1, 3, 5):
        inboxes.subgame_results.put(settled_payload(n, series_id="series-1"))

    monkeypatch.setattr(
        scheduler.ts_coordinator,
        "start_coordinator",
        lambda *args: (inboxes, None),
    )
    monkeypatch.setattr(scheduler.ts_client, "TeamSyncClient", FakeSiblingClient)
    FakeSiblingClient.fail_on = set()
    agent, _events = agent_with_events(tmp_path, num_games=6)
    agent.config._data.setdefault("team_sync", {})["start_role"] = "thief"
    monkeypatch.setattr(
        agent,
        "build_runtime",
        lambda sub_game_number, controls=None: SimpleNamespace(
            run=lambda: police_summary(sub_game_number)
        ),
    )
    mailed = []
    agent.email_report = lambda paths: mailed.append(paths) or "sent"

    summaries = scheduler.run_team_series(agent, base=tmp_path)

    assert [summary["role"] for summary in summaries] == [
        "thief",
        "police",
        "thief",
        "police",
        "thief",
        "police",
    ]
    assert len(mailed) == 1
