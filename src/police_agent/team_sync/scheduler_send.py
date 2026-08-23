"""Outbound series messages to the sibling process, and the ack that follows.

Split from `scheduler_helpers.py` to keep both inside the 150-line budget, and
along a real seam rather than an arbitrary one: everything here writes to the
sibling link, while what is left next door decides *when* a write should happen.

The `TypeError` fallbacks are one idea in two places. A sibling build older than
role negotiation has no `start_role`/`next_role` parameters, and calling it with
them is a `TypeError` before any message leaves -- so retrying without them is
safe, and it degrades to a series the old build can still play rather than to a
transport error nobody can act on.
"""

from police_agent.team_sync.scheduler_wait import wait_for_ack
from police_agent.team_sync.state import role_for_subgame


def send_series_start(client, series_id, game_id, total, first, start_role):
    """Announce the series to the sibling, tolerating a client without role kwargs."""
    next_role = role_for_subgame(first, start_role)
    try:
        return client.send_series_start(
            series_id, game_id, total, first, start_role=start_role, next_role=next_role
        )
    except TypeError:
        return client.send_series_start(series_id, game_id, total, first)


def send_handoff(client, series_id, completed, next_subgame, start_role, next_role):
    """Hand the next sub-game to the sibling, with the same older-client fallback."""
    try:
        return client.send_handoff(
            series_id, completed, next_subgame, start_role=start_role, next_role=next_role
        )
    except TypeError:
        return client.send_handoff(series_id, completed, next_subgame)


def wait_for_sibling_ack(inboxes, client, series_id: str, sub_game_number: int) -> None:
    """Block until the sibling acks our last message, when both sides support acks.

    Real clients expose the outbound message id and real inboxes collect acks;
    older test doubles do neither, and for those this is a no-op rather than a
    failure -- there is nothing to wait for, not an ack that went missing.
    """
    message_id = getattr(client, "last_message_id", "")
    if message_id and hasattr(inboxes, "acks"):
        wait_for_ack(inboxes, series_id, message_id, sub_game_number)
