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


def wait_for_series_start(
    inboxes,
    start_role: str,
    expected_sub_game: int = 1,
    expected_role: str = "thief",
    sender_role: str = "thief",
) -> dict:
    """Wait for the opening announcement for the expected sub-game."""
    deadline = time.monotonic() + WAIT_FOR_SIBLING_SECONDS
    inbox = getattr(inboxes, "series_start", None)
    if inbox is None:
        raise TransportError("team_sync coordinator has no series_start inbox")
    while time.monotonic() < deadline:
        try:
            message = inbox.get(timeout=INBOX_POLL_SECONDS)
        except queue.Empty:
            continue
        if (
            isinstance(message, dict)
            and message.get("sender_role") == sender_role
            and message.get("start_role") == start_role
            and message.get("sub_game_number") == expected_sub_game
            and message.get("next_role") == expected_role
        ):
            return message
        print(f"team_sync: rejected series_start: {message!r}", file=sys.stderr)
    raise TransportError(f"No series_start within {WAIT_FOR_SIBLING_SECONDS}s")


def wait_for_ack(inboxes, series_id: str, message_id: str, sub_game_number: int) -> None:
    """Wait for the sibling to consume one unlock, rejecting stale ACKs."""
    deadline = time.monotonic() + WAIT_FOR_SIBLING_SECONDS
    while time.monotonic() < deadline:
        try:
            message = inboxes.acks.get(timeout=INBOX_POLL_SECONDS)
        except queue.Empty:
            continue
        if (
            isinstance(message, dict)
            and message.get("series_id") == series_id
            and message.get("sub_game_number") == sub_game_number
            and message.get("ack_for_message_id", message.get("in_reply_to")) == message_id
        ):
            return
        print(f"team_sync: rejected stale ACK: {message!r}", file=sys.stderr)
    raise TransportError(
        f"No ACK for sub-game {sub_game_number} within {WAIT_FOR_SIBLING_SECONDS}s"
    )


def wait_for_handoff(inboxes, series_id: str, next_subgame: int) -> dict:
    """Consume the Thief-owned handoff that unlocks Police's next game."""
    deadline = time.monotonic() + WAIT_FOR_SIBLING_SECONDS
    inbox = getattr(inboxes, "handoff", None)
    if inbox is None:
        raise TransportError("team_sync coordinator has no handoff inbox")
    while time.monotonic() < deadline:
        try:
            message = inbox.get(timeout=INBOX_POLL_SECONDS)
        except queue.Empty:
            continue
        if (
            isinstance(message, dict)
            and message.get("series_id") == series_id
            and message.get("sender_role") == "thief"
            and message.get("next_subgame", message.get("sub_game_number")) == next_subgame
        ):
            return message
        print(f"team_sync: rejected out-of-order handoff: {message!r}", file=sys.stderr)
    raise TransportError(
        f"No handoff for sub-game {next_subgame} within {WAIT_FOR_SIBLING_SECONDS}s"
    )
