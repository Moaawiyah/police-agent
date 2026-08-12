"""McpTransport's public operations, split out to keep the class itself --
`_call`/`_send_with_retry` plus construction -- under the file's line budget.

Each function takes the transport (`link`) as its first argument and calls
back into `link._call`/`link._send_with_retry`, so instance-level monkeypatching
of those two (see tests/infra/test_mcp_client.py) still reaches every caller
here exactly as it would a bound method.
"""

import contextlib
import queue

from police_agent.exceptions import TransportError


def exchange_agreement(link, signed: dict) -> dict:
    """Send my signed agreement and block until the opponent's arrives.

    The handshake is where startup skew is largest, so it waits the full
    connect budget rather than the shorter per-turn reply budget.
    """
    link._send_with_retry("negotiate", {"message": signed})
    try:
        return link._inboxes.agreements.get(timeout=link._connect_timeout)
    except queue.Empty as exc:
        raise TransportError(f"No agreement from the opponent at {link._url}") from exc


def send_turn(link, message: dict) -> None:
    """Hand my turn -- and with it the right to move -- to the opponent."""
    link._send_with_retry("receive_turn", {"message": message})


def poll_turn(link, timeout: float) -> dict | None:
    """Wait for the opponent's turn. None means it ran out of time, not that it lost."""
    try:
        return link._inboxes.turns.get(timeout=timeout)
    except queue.Empty:
        return None


def poll_control(link) -> dict | None:
    """Take one advisory session signal if any is waiting; never blocks the game."""
    try:
        return link._inboxes.controls.get_nowait()
    except queue.Empty:
        return None


def send_control(link, message: dict) -> None:
    """Best-effort control send: a short timeout and swallowed errors, since
    this is advisory only and must never stall the game the way a missed
    turn or audit reveal would."""
    with contextlib.suppress(Exception):
        link._call("receive_control", {"message": message}, timeout=link._control_send_timeout)


def exchange_audit(link, payload: dict) -> dict | None:
    """Reveal my sealed records and collect the opponent's, if it still answers.

    The send is best-effort on a short budget: a peer that already knows it
    won may exit the moment it has read its inbox, killing its server while
    our call is in flight even though the payload landed. Their reveal may
    well be sitting in our inbox regardless, so we always look.
    """
    with contextlib.suppress(TransportError):
        link._send_with_retry("submit_audit", {"payload": payload}, link._audit_send_timeout)
    try:
        return link._inboxes.audits.get(timeout=link._reply_timeout)
    except queue.Empty:
        return None


def drain_inboxes(link) -> None:
    """Discard stale mail so a restarted sub-game cannot inherit the last one's.

    Agreements are left alone: both peers drain before re-negotiating, and no
    turn is sent until the fresh handshake has completed, so a queued
    agreement here is always the new one.
    """
    for inbox in (link._inboxes.turns, link._inboxes.controls, link._inboxes.audits):
        with contextlib.suppress(queue.Empty):
            while True:
                inbox.get_nowait()
