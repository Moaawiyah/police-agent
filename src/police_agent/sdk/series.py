"""`PoliceAgentSDK.play_series`, split out to keep `agent.py` under the
project's line budget. Functions take the agent as their first argument,
same delegation idiom `peer/runtime_loop.py` uses for `PoliceRuntime`.
"""

from police_agent.peer.series import run_series
from police_agent.report.result import scoring_from
from police_agent.report.result_parts import series_totals


def play_series(agent) -> list[dict]:
    """Play every sub-game of the agreed series over one held connection.

    Each sub-game's own `game_over` is relabelled `sub_game_over` on the way
    to the listener -- the GUI already treats `game_over` as "the whole
    match is finished" (see `gui/player.py::_drain`), and only the series as
    a whole is that. A real `game_over` is raised once more, here, after the
    last sub-game actually ends.

    When `team_sync.enabled` is set, this delegates to the team_sync
    scheduler instead: only Police's own sub-games are played here, the
    sibling Thief process's are imported over the local coordination link.
    Imported lazily so the two modules can import each other's small,
    reused helpers (`series_listener` below) without a circular import at
    module load time -- this branch is the only place that matters.
    """
    if agent.config.get("team_sync.enabled"):
        from police_agent.team_sync.scheduler import run_team_series

        return run_team_series(agent)
    summaries = run_series(
        agent.config,
        agent.connect(),
        listener=series_listener(agent),
        controls=agent.controls,
        league=agent.options.league,
    )
    if agent.listener is not None:
        totals = series_totals(summaries, scoring_from(agent.config))
        agent.listener(
            {
                "type": "game_over",
                "summary": summaries[-1],
                "summaries": summaries,
                "sub_game_number": len(summaries),
                "totals": totals,
            }
        )
    return summaries


def series_listener(agent):
    """Wrap `agent.listener` so each sub-game's `game_over` becomes `sub_game_over`."""
    if agent.listener is None:
        return None

    def relabel(event: dict) -> None:
        """Relabel one sub-game's `game_over` event before forwarding it."""
        if event.get("type") == "game_over":
            agent.listener({**event, "type": "sub_game_over"})
            return
        agent.listener(event)

    return relabel
