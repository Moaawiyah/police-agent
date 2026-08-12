"""A scripted stand-in for the thief's side of the wire.

Implements the same surface as `McpTransport` -- which is the point of keeping
that surface small -- so the whole turn loop can be driven with no sockets, no
threads and no second process. It is a test double and lives under `tests/`
deliberately: the specification (ch. 2.4.2) forbids the thief ever being an
in-process object at runtime, and this must never become shipped agent code.
"""

from police_agent.peer.sealing import now_iso
from police_agent.shared.rate_limit import DosDetector


class FakeTransport:
    """Replays a fixed script of thief turns and records everything sent."""

    def __init__(
        self,
        incoming=None,
        agreement=None,
        audit=None,
        incoming_controls=None,
        dos_limit_per_minute: float = 6000.0,
    ) -> None:
        self.incoming = list(incoming or [])
        self._agreement = agreement
        self._audit = audit
        self._incoming_controls = list(incoming_controls or [])
        self.sent_turns: list[dict] = []
        self.sent_audits: list[dict] = []
        self.sent_controls: list[dict] = []
        self.agreement_sent: dict | None = None
        # No real FastMCP server sits in front of a FakeTransport, so nothing
        # ever records against this -- it exists only so PeerRuntime's
        # unconditional `transport.inbound_dos` read has something to find.
        self.inbound_dos = DosDetector(dos_limit_per_minute)

    def exchange_agreement(self, signed: dict) -> dict:
        """Echo the police's own agreement back by default: an opponent that
        agreed to exactly the same terms, which is the case the handshake is
        supposed to accept."""
        self.agreement_sent = signed
        return self._agreement if self._agreement is not None else dict(signed)

    def send_turn(self, message: dict) -> None:
        self.sent_turns.append(message)

    def poll_turn(self, timeout: float) -> dict | None:
        """The next scripted turn, or None once the script runs out -- which is
        exactly what a silent opponent looks like to the runtime."""
        return self.incoming.pop(0) if self.incoming else None

    def exchange_audit(self, payload: dict) -> dict | None:
        self.sent_audits.append(payload)
        return self._audit

    def poll_control(self) -> dict | None:
        return self._incoming_controls.pop(0) if self._incoming_controls else None

    def send_control(self, message: dict) -> None:
        self.sent_controls.append(message)

    def drain_inboxes(self) -> None:
        pass


def thief_turn(step: int, **fields) -> dict:
    """One turn message as the thief would send it."""
    message = {
        "step": step,
        "sender": "thief",
        "hint": "",
        "smell_grid": {},
        "commit": f"thief-commit-{step}",
        "timestamp": now_iso(),
        "barrier_placed": None,
        "capture_claim": None,
        "claim_response": None,
        "win_claim": None,
    }
    message.update(fields)
    return message


def thief_turns(count: int, **fields) -> list[dict]:
    """A run of `count` ordinary thief turns, so a test can reach the ceiling."""
    return [thief_turn(step, **fields) for step in range(1, count + 1)]
