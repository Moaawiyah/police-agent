"""Blocking, event/queue-based wait for the sibling Thief's settled result.

Split out of `scheduler.py` to keep it under the project's line budget.
Never sleep-polls: each round blocks on `queue.Queue.get(timeout=...)`, the
same idiom `infra/mcp_client.py` already uses for the opponent-facing link.
"""

import queue
import sys
import time

from police_agent.exceptions import TransportError

INBOX_POLL_SECONDS = 2.0  # one bounded queue.get() at a time -- never a sleep-poll
WAIT_FOR_SIBLING_SECONDS = 3600.0  # a whole sub-game may legitimately take this long


def wait_for_thief_result(inboxes, series_id: str, sub_game_number: int) -> dict:
    """Block for the expected `subgame_result`; drop and log any other."""
    deadline = time.monotonic() + WAIT_FOR_SIBLING_SECONDS
    while time.monotonic() < deadline:
        try:
            message = inboxes.subgame_results.get(timeout=INBOX_POLL_SECONDS)
        except queue.Empty:
            continue
        if _is_expected(message, series_id, sub_game_number):
            return message
        print(f"team_sync: rejected out-of-order subgame_result: {message!r}", file=sys.stderr)
    raise TransportError(
        f"No subgame_result for sub-game {sub_game_number} within {WAIT_FOR_SIBLING_SECONDS}s"
    )


def _is_expected(message: object, series_id: str, sub_game_number: int) -> bool:
    """Strict ordering: right series, right sender, right sub-game number."""
    return (
        isinstance(message, dict)
        and message.get("series_id") == series_id
        and message.get("sender_role") == "thief"
        and message.get("sub_game_number") == sub_game_number
    )
