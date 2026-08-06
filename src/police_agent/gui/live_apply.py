"""Turning one runtime event into what the window shows.

Split from `player.py` so the app is left holding only its lifecycle -- thread,
queue, clock -- and so this half can be tested against a stub window with no Tk
and no game. It takes the window rather than the app for the same reason: what
an event should *look like* does not depend on how the app was started.

Every branch is one event type the runtime publishes. An unrecognised type
renders its view and nothing else, which is what makes adding an event to the
runtime a safe change rather than a crash in a thread nobody is watching.
"""

from police_agent.gui.game_mode import NO_MODEL

BANNER_ERROR = "ERROR - see status"


def apply_event(window, event: dict) -> None:
    """Render one runtime event. The window is only ever touched from here."""
    kind = event["type"]
    if kind == "error":
        window.set_turn(False, BANNER_ERROR)
        window.set_label("status", event["message"])
        return
    if "view" in event:
        window.render(event["view"])
    if kind == "negotiated":
        _apply_negotiated(window, event)
    elif kind == "incoming":
        _apply_incoming(window, event)
    elif kind == "replay_ignored":
        window.set_label("status", f"replayed turn {event['step']} ignored (not answered)")
    elif kind == "moved":
        _apply_moved(window, event)
    elif kind == "game_over":
        _apply_game_over(window, event)


def _apply_negotiated(window, event: dict) -> None:
    """The handshake passed. The thief opens, so this peer waits first."""
    peer = event.get("peer") or {}
    window.set_label("status", "Terms agreed and signature verified (SHA-256)")
    window.set_label("hint_in", f"opponent: {peer.get('group_id', 'unknown')}")
    window.set_turn(False)


def _apply_incoming(window, event: dict) -> None:
    """A turn arrived, and with it the right to move: the banner goes green."""
    window.set_label("hint_in", f"step {event['step']}: {event.get('hint') or '(silent)'}")
    window.set_turn(True)


def _apply_moved(window, event: dict) -> None:
    decision = event["decision"]
    window.set_label("hint_out", f"step {event['view']['step']}: {event.get('hint') or '(silent)'}")
    window.set_label("verdict", decision.rationale)
    # Only the digest is shown, and only its head. The whole point of the
    # commitment is that this is all the opponent gets until the audit, so a
    # screenshot of this window must not leak more than the wire did.
    window.set_label("commit", f"{event['commit'][:32]}...")
    window.set_turn(False)


def _apply_game_over(window, event: dict) -> None:
    summary = event["summary"]
    audit = summary["audit"]
    winner = summary["winner"] or "nobody"
    window.set_turn(False, f"GAME OVER: {summary['result']} - winner {winner.upper()}")
    window.set_label("status", _audit_line(audit, summary))
    window.set_label("reliability", _reliability_line(summary))
    window.set_label("tokens", _tokens_line(summary))


def _tokens_line(summary: dict) -> str:
    """The series-mandatory total (Appendix He 54), shown once at game over --
    not live, since the shipped model is free and there is nothing to meter."""
    tokens = summary.get("tokens") or {}
    calls = tokens.get("model_calls", 0)
    if not calls:
        return "0 (no model calls)"
    return (
        f"{tokens.get('tokens_total', 0)} across {calls} call{'s' if calls != 1 else ''} "
        f"({tokens.get('prompt_tokens', 0)} prompt / {tokens.get('completion_tokens', 0)} completion)"
    )


def _audit_line(audit: dict, summary: dict) -> str:
    """What the end-of-game audit proved, in the one line there is room for."""
    if audit.get("skipped"):
        outcome = "not exchanged (opponent silent)"
    else:
        outcome = f"{'PASSED' if audit['passed'] else 'FAILED'}, {audit['verified_steps']} steps"
    return f"Audit {outcome} | {summary['steps']} steps | {summary['duration_seconds']}s"


def _reliability_line(summary: dict) -> str:
    """How far the thief's hints survived contact with its own scent trail."""
    reliability = summary.get("opponent_reliability")
    if reliability is None:
        return NO_MODEL
    judgement = "believable" if reliability >= 0.5 else "talked itself into disbelief"
    return f"{reliability:.2f} - {judgement}"
