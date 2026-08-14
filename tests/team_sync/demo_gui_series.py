"""Watch a whole six-sub-game team_sync series in the live window.

    uv run python -m tests.team_sync.demo_gui_series

Police opens the series and owns sub-games 1/3/5 -- those are played for
real on the board, against the scripted opponent from `scripted_opponent.py`.
Sub-games 2/4/6 belong to the sibling thief_agent process, so the window
shows what it shows in a real match: WAITING, then the imported result.

Not a pytest module (no `test_` prefix, never collected): it opens a Tk
window and waits for a human to press Start. Nothing here touches a socket,
no report is mailed, and the artifacts land under `logs/OURTEAM/`.
"""

import os

from police_agent.sdk import PoliceAgentSDK
from police_agent.team_sync import scheduler
from tests.conftest import config_with
from tests.team_sync.scripted_opponent import ScriptedOpponent
from tests.team_sync.sibling_simulator import SiblingThiefProcess, SimulatedInboxes

SECRET = "demo-team-sync-secret"
TOTAL = 6
START_ROLE = "police"


def build_agent() -> PoliceAgentSDK:
    """The real SDK, with the opponent and the sibling process stood in for."""
    os.environ["TEAM_SYNC_SECRET"] = SECRET
    config = config_with(
        game__group_id="OURTEAM",
        game__num_games=TOTAL,
        team_sync__enabled=True,
        team_sync__start_role=START_ROLE,
        # `config_with` builds from the shared, signed `game.json` only, so the
        # private keys the window reads for its title bar and menu are set here.
        # Nothing dials the opponent URL: the transport is injected.
        network__my_port=8801,
        network__opponent_url="in-process scripted opponent",
        gui__step_seconds=0.15,
    )
    inboxes = SimulatedInboxes()
    sibling = SiblingThiefProcess(inboxes, SECRET, TOTAL, START_ROLE)
    # The sibling normally answers over 127.0.0.1:8812; here it answers in
    # process, so the demo needs no second terminal and no second repo.
    scheduler.ts_coordinator.start_coordinator = lambda *_args: (inboxes, None)
    scheduler.ts_client.TeamSyncClient = lambda *_args, **_kwargs: sibling

    agent = PoliceAgentSDK(config=config, transport=ScriptedOpponent())
    agent.email_report = lambda paths: print(f"[demo] report written, not mailed: {paths}")
    return agent


def main() -> None:
    """Open the window and play the series when Start is pressed."""
    from police_agent.gui.player import LivePeerApp

    print(f"team_sync demo: {TOTAL} sub-games, {START_ROLE} opens.")
    print("Police plays 1/3/5 on the board; 2/4/6 arrive from the sibling process.")
    print("Press Start in the window.\n")
    summaries = LivePeerApp(build_agent()).run()
    for index, summary in enumerate(summaries, start=1):
        owner = summary.get("role", "?")
        source = "played here" if owner == "police" else "imported from sibling"
        print(f"  G{index}  {owner:<7} {source:<22} {summary.get('result', '-')}")


if __name__ == "__main__":
    main()
