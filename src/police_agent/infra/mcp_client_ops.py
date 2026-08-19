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

# Fixed rather than read from config: the handshake is where startup skew is
# largest, and this budget must hold regardless of what network.watchdog_
# timeout_seconds is set to for the rest of the connection.
NEGOTIATE_TIMEOUT_SECONDS = 180.0


def greeting_in(reply) -> dict | None:
    """The opponent's own greeting, if its dialect carried one in the reply body.

    Shape-checked rather than trusted: `terms` and `nonce` are what
    `Negotiation.verify_peer` needs, so anything without them is an
    acknowledgement (`{"ok": true}`), not an agreement.
    """
    if not isinstance(reply, dict):
        return None
    message = reply.get("message")
    if isinstance(message, dict) and "terms" in message and "nonce" in message:
        return message
    return None


def exchange_agreement(link, signed: dict) -> dict:
    """Send my signed agreement and return the opponent's, by either dialect.

    The handshake is where startup skew is largest, so it waits a fixed
    180s budget rather than the shorter per-turn reply budget.

    Publishing my greeting first is what lets my own negotiate tool answer a
    peer that reads reply bodies. Reading the reply is the mirror of that: a
    peer which only answers in-band never dials back, so the reply is the only
    copy of its agreement I will ever see. The inbox remains the fallback, and
    is still the path a push peer takes.
    """
    link.publish_greeting(signed)
    reply = link._send_with_retry(
        "negotiate", {"message": signed}, timeout=NEGOTIATE_TIMEOUT_SECONDS
    )
    peer = greeting_in(reply)
    if peer is not None:
        # A both-dialects peer (it pushes AND answers) leaves a duplicate behind;
        # dropping it here stops the NEXT sub-game's handshake from completing
        # instantly against this one's stale copy.
        with contextlib.suppress(queue.Empty):
            link._inboxes.agreements.get_nowait()
        return peer
    try:
        return link._inboxes.agreements.get(timeout=NEGOTIATE_TIMEOUT_SECONDS)
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
