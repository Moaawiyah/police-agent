"""ControlLink: this peer's side of the opt-in bidirectional control channel.

Pure coordination logic over an injected transport (`send_control`/`poll_control`)
and a `GameControls`. The channel is ACTIVE only when BOTH peers have enabled
it. While active it shares live status and honours a restart (auto-approved)
and a clean quit. No Tk and no threads here, so it is fully unit-testable.

Advisory only, by `peer/protocol.py`'s own design: nothing here is committed
or audited, and a control message can never change a score. `restart`
abandons the current sub-game the same way the existing Stop button already
does -- it just also rebuilds a fresh one afterward, on both sides.

Mirrors the thief repository's module of the same name so the two speak the
same wire format; police was previously receive-only here, by an earlier,
explicit design choice this now supersedes on request.
"""

from typing import Any

from police_agent.peer.protocol import ControlMessage

# Statuses a peer broadcasts (turn-phase + control overlay).
WAITING, THINKING, PLAYING = "WAITING", "THINKING", "PLAYING"
PAUSED, STOPPED, GAME_OVER, QUIT = "PAUSED", "STOPPED", "GAME_OVER", "QUIT"

__all__ = [
    "WAITING",
    "THINKING",
    "PLAYING",
    "PAUSED",
    "STOPPED",
    "GAME_OVER",
    "QUIT",
    "ControlLink",
]


class ControlLink:
    """Enable-handshake + status/restart/quit signalling for this peer."""

    def __init__(self, role: str, transport, controls, listener=None) -> None:
        self._role = role
        self._transport = transport
        self._controls = controls
        self._listen = listener or (lambda event: None)
        self._i_enabled = False
        self._peer_enabled = False
        self._opponent: dict[str, Any] = {"status": "-", "sub_game_number": None}
        self._last_status: str | None = None
        self._pending_restart = False  # a peer restart, approved, awaiting the runtime
        self._opponent_quit = False

    @property
    def active(self) -> bool:
        """True only once BOTH sides have enabled the channel."""
        return self._i_enabled and self._peer_enabled

    @property
    def i_enabled(self) -> bool:
        return self._i_enabled

    @property
    def opponent(self) -> dict:
        return dict(self._opponent)

    @property
    def opponent_quit(self) -> bool:
        return self._opponent_quit

    def take_pending_restart(self) -> bool:
        """Consume a peer-approved restart (True once), so the runtime restarts."""
        if self._pending_restart:
            self._pending_restart = False
            return True
        return False

    def enable(self) -> None:
        """Local user opted in; announce it so the peer can match (then active)."""
        self._i_enabled = True
        self._send("enable")

    def broadcast_status(self, status: str, sub_game_number: int) -> None:
        """Record + send my status, but only on change (never spam the wire)."""
        self._controls.set_status(status)
        if not self._i_enabled or status == self._last_status:
            return
        self._last_status = status
        self._send("status", status=status, sub_game_number=sub_game_number)

    def send_restart(self) -> None:
        self._send("restart")

    def send_quit(self) -> None:
        self._send("quit", status=QUIT)

    def drain(self) -> list[dict[str, Any]]:
        """Process every pending inbound control message; return handler events."""
        poll = getattr(self._transport, "poll_control", None)
        if poll is None:
            return []
        events: list[dict[str, Any]] = []
        while (raw := poll()) is not None:
            events.append(self._handle(ControlMessage.from_dict(raw)))
        return events

    def _handle(self, msg: ControlMessage) -> dict[str, Any]:
        event: dict[str, Any]
        if msg.kind == "enable":
            self._peer_enabled = True
            event = {"type": "control_enable", "sender": msg.sender}
        elif msg.kind == "status":
            self._opponent = {"status": msg.status, "sub_game_number": msg.sub_game_number}
            event = {"type": "control_status", **self._opponent}
        elif msg.kind == "restart":
            if self.active:  # auto-approve when both enabled
                self._pending_restart = True
            event = {"type": "control_restart", "granted": self.active}
        elif msg.kind == "quit":
            self._opponent["status"] = QUIT
            self._opponent_quit = True
            event = {"type": "control_quit", "sender": msg.sender}
        else:
            event = {"type": "control_unknown", "kind": msg.kind}
        self._listen(event)
        return event

    def _send(self, kind: str, **fields) -> None:
        send = getattr(self._transport, "send_control", None)
        if send is not None:
            send(ControlMessage(kind=kind, sender=self._role, **fields).to_dict())
