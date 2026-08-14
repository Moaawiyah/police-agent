"""The shared harness for a whole-series team_sync run.

One place to build the agent and play the series, so `test_full_series.py`
(what the series produces) and `test_series_banners.py` (what the window is
told while it happens) stay within the project's per-file line budget without
either of them owning the other's setup.
"""

import pytest

from police_agent.sdk import PoliceAgentSDK
from police_agent.team_sync import scheduler
from police_agent.team_sync.security import ENV_VAR
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
