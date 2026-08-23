"""The scheduler's reporting/role helpers, split out of `scheduler_helpers.py`
to keep both inside the project's 150-line budget. Nothing here decides
*when* the sibling is written to (that's the rest of `scheduler_helpers.py`
and `scheduler_send.py`) -- this is what a turn of the loop tells the GUI, and
which role this process opens the series playing.
"""

from police_agent.report.result import scoring_from
from police_agent.report.result_parts import series_totals
from police_agent.team_sync.state import POLICE, THIEF


def notify_game_over(agent, summaries: list[dict]) -> None:
    """The same final `game_over` event the single-process path emits."""
    if agent.listener is None:
        return
    totals = series_totals(summaries, scoring_from(agent.config))
    agent.listener(
        {
            "type": "game_over",
            "summary": summaries[-1] if summaries else {},
            "summaries": summaries,
            "sub_game_number": len(summaries),
            "totals": totals,
        }
    )


def group_id(config) -> str:
    """This team's agreed group id, or a named placeholder when unconfigured.

    Falling back rather than raising: a missing group id should not abort a
    local practice series, and the placeholder is obvious in a result artifact.
    """
    return str(config.get("game.group_id", "unknown-group"))


def notify_status(agent, status: str, sub_game_number: int) -> None:
    """A team_sync-kind event for statuses no `PoliceRuntime` event covers --
    chiefly the even sub-games, which this process never plays itself."""
    if agent.listener is not None:
        agent.listener(
            {
                "type": "team_sync",
                "status": status,
                "state": status,
                "sub_game_number": sub_game_number,
            }
        )


def start_role(config, settings) -> str:
    """Which role this process plays in sub-game 1, from the first key that has it.

    Three spellings are accepted because the key moved between config layouts,
    but an unrecognised *value* raises: silently defaulting the start role would
    put both siblings on the same side for half the series.
    """
    value = config.get("team_sync.start_role")
    if value is None:
        value = config.get(
            "start_role", config.get("game.start_role", settings.get("start_role", "police"))
        )
    if value not in (POLICE, THIEF):
        raise ValueError("team_sync.start_role must be 'police' or 'thief'")
    return value
