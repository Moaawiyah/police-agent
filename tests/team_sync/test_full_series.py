"""The whole six-sub-game series, end to end through `run_team_series`.

Police opens the series and owns sub-games 1/3/5; the sibling thief_agent
process owns 2/4/6 and its settled results are imported. Nothing here plays
one of our repos against the other: the opponent is a scripted transport
standing in for the third-party peer, and the sibling is reachable only over
the team_sync wire (`sibling_simulator.py`).

Run it with `-s` to watch the flow print itself.
"""

import pytest

from police_agent.sdk import PoliceAgentSDK
from police_agent.team_sync import scheduler
from police_agent.team_sync.security import ENV_VAR
from police_agent.team_sync.store import TeamSyncStore
from tests.conftest import config_with
from tests.team_sync.scripted_opponent import ScriptedOpponent
from tests.team_sync.sibling_simulator import install

SECRET = "shared-team-sync-secret"
TOTAL = 6


@pytest.fixture
def police(tmp_path, monkeypatch):
    """A real `PoliceAgentSDK` over the scripted opponent, wired for team_sync."""
    monkeypatch.setenv(ENV_VAR, SECRET)
    config = config_with(
        game__group_id="OURTEAM",
        game__num_games=TOTAL,
        rules__max_steps=2,
        rules__survival_threshold=2,
    )
    agent = PoliceAgentSDK(config=config, transport=ScriptedOpponent())
    events: list = []
    agent.listener = events.append
    mailed: list = []
    agent.email_report = mailed.append
    return agent, events, mailed


def run(police, tmp_path, monkeypatch):
    """Play the whole series and hand back everything the run produced."""
    agent, events, mailed = police
    sibling = install(monkeypatch, scheduler, SECRET, total=TOTAL)
    summaries = scheduler.run_team_series(agent, base=tmp_path)
    return summaries, events, mailed, sibling


def test_a_full_six_subgame_series_alternates_police_and_thief(police, tmp_path, monkeypatch):
    summaries, events, _mailed, _sibling = run(police, tmp_path, monkeypatch)

    print_flow(summaries, events)
    assert len(summaries) == TOTAL
    assert [summary["role"] for summary in summaries] == ["police", "thief"] * 3
    numbers = [summary["step_zero"]["sub_game_number"] for summary in summaries]
    assert numbers == [1, 2, 3, 4, 5, 6]


def test_only_the_subgame_owner_opens_it_on_the_wire(police, tmp_path, monkeypatch):
    """The sibling's sub-games are waited for, never played here as well.

    The peer-facing wire is role-split: an opponent whose role alternates
    plays its Police in sub-game 2, and a second Police opened here would
    collide with it on role rather than play it.
    """
    agent, _events, _mailed = police
    played: list[int] = []
    build = agent.build_runtime
    monkeypatch.setattr(
        agent, "build_runtime", lambda n, **kwargs: (played.append(n), build(n, **kwargs))[1]
    )

    run(police, tmp_path, monkeypatch)

    assert played == [1, 3, 5]
    assert len(agent._transport.sent_audits) == 3  # one per sub-game actually played


def test_every_subgame_is_filed_under_one_game_id(police, tmp_path, monkeypatch):
    """Police's own sub-games and the imported ones join into one series."""
    run(police, tmp_path, monkeypatch)

    records = sorted(path.name for path in (tmp_path / "OURTEAM").glob("record_*.json"))
    assert records == [f"record_OURTEAM-vs-THEIRTEAM_g0{n}.json" for n in range(1, TOTAL + 1)]


def test_the_wire_carries_one_opening_and_a_handoff_per_police_subgame(
    police, tmp_path, monkeypatch
):
    """Police announces the series once, hands off after each sub-game it owns,
    acknowledges each handoff the sibling sends back, and closes the series."""
    _summaries, _events, _mailed, sibling = run(police, tmp_path, monkeypatch)

    assert sibling.received == [
        ("series_start", 1),
        ("handoff", 2),  # sub-game 1 settled -> the sibling's sub-game 2 is unlocked
        ("ack", 3),  # the sibling's own handoff back to Police, acknowledged
        ("handoff", 4),
        ("ack", 5),
        ("handoff", 6),
        ("series_complete", TOTAL),
    ]


def test_the_series_ends_settled_and_is_reported_exactly_once(police, tmp_path, monkeypatch):
    """The binding report is mailed on the last sub-game, and only then."""
    _summaries, events, mailed, _sibling = run(police, tmp_path, monkeypatch)

    status = TeamSyncStore(tmp_path / "OURTEAM" / "team_sync").load_status()
    assert status.state == "series_complete"
    assert status.sub_game_number == TOTAL
    assert len(mailed) == 1
    assert [event["type"] for event in events].count("game_over") == 1


def test_the_gui_is_told_who_is_playing_each_subgame(police, tmp_path, monkeypatch):
    """A sub-game this process does not own still reports progress to the window."""
    _summaries, events, _mailed, _sibling = run(police, tmp_path, monkeypatch)

    states = [
        (event["state"], event["sub_game_number"])
        for event in events
        if event["type"] == "team_sync"
    ]
    assert ("WAITING", 2) in states  # the sibling owns sub-game 2
    assert ("READY", 3) in states  # ...and Police is unlocked for sub-game 3
    assert ("SERIES_COMPLETE", TOTAL) in states


def print_flow(summaries: list[dict], events: list[dict]) -> None:
    """The series as a table: who owned each sub-game, and how it settled."""
    print(f"\n  team_sync series -- {TOTAL} sub-games, Police opens\n")
    print("   sub  owner   source                 result     winner")
    for index, summary in enumerate(summaries, start=1):
        owner = summary["role"]
        source = "played here" if owner == "police" else "imported from sibling"
        print(
            f"   G{index:<3} {owner:<7} {source:<22} {summary['result']:<10} "
            f"{summary.get('winner') or '-'}"
        )
    totals = next(event for event in events if event["type"] == "game_over")["totals"]
    print(f"\n   totals {totals}\n")
