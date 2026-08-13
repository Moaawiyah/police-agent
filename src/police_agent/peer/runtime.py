"""PoliceRuntime: one police agent's whole life, from handshake to audit.

negotiate -> wait for the thief's turn -> fold it in -> decide and send -> repeat
-> reveal and verify. There is no referee and no central loop; each peer runs
this independently and the two only meet at the transport.

The thief opens. The police therefore *waits first*, and a turn arriving is what
makes it this peer's move -- the message is the turn token. A peer that sent
before hearing would be playing two turns in a row.

The brain, the belief map and the scent field are all injected rather than built
in place. Each has a working default, so the shipped agent needs no wiring; the
seam exists because it is what lets the whole loop be tested against a fake
transport and a scripted estimate, with no sockets and no opponent involved.
Construction itself is delegated to `runtime_build.wire`, split out to keep
this file under the project's line budget.
"""

import time

from police_agent.peer.handshake import identity_from_config, negotiate
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.runtime_build import wire
from police_agent.peer.runtime_loop import (
    apply_incoming,
    ceiling_result,
    notify,
    turn_loop,
    turn_timeout,
)
from police_agent.peer.summary import build_summary, exchange_and_audit


class PoliceRuntime:
    """Runs the police side of one sub-game against a remote thief."""

    def __init__(
        self,
        config,
        transport,
        brain=None,
        threat=None,
        scent=None,
        hint_writer=None,
        analyst=None,
        listener=None,
        controls=None,
        league: bool = False,
        link=None,
        sub_game_number: int | None = None,
        watchdog=None,
    ) -> None:
        """Wire this sub-game's collaborators via `runtime_build.wire`."""
        wire(
            self,
            config,
            transport,
            sub_game_number,
            league,
            brain=brain,
            threat=threat,
            scent=scent,
            hint_writer=hint_writer,
            analyst=analyst,
            listener=listener,
            controls=controls,
            link=link,
            watchdog=watchdog,
        )

    def notify(self, event: dict) -> None:
        """Forward `event` to the listener, if one was given."""
        notify(self, event)

    def _set_abort_reason(self, reason: str) -> None:
        self.abort_reason = reason

    def run(self) -> dict:
        """Play one sub-game to a result and return the match summary."""
        # Handing over the declaration's digest here is what makes it binding:
        # the opponent holds it before the first move and can recompute it from
        # the payload and nonce revealed at the audit.
        self.peer_identity = negotiate(
            self.terms,
            identity_from_config(self.config, self.records[0]["commit"]),
            self.transport,
        )
        self.started_monotonic = time.monotonic()  # the clock starts at agreement
        self.notify({"type": "negotiated", "peer": self.peer_identity})

        self.watchdog.start()
        try:
            self._turn_loop()
        finally:
            # A restart unwinds this uncaught (RestartRequested) -- the
            # watchdog must still be joined before that propagates, or a
            # stale thread could later call stop() against the *next*
            # sub-game's GameControls, which run_series shares across the
            # whole series.
            self.watchdog.stop()
        result, winner = self._result
        result, winner, audit, opponent_records = exchange_and_audit(self, result, winner)
        summary = build_summary(self, result, winner, audit, opponent_records)
        self.notify({"type": "game_over", "summary": summary})
        return summary

    def _turn_loop(self) -> None:
        turn_loop(self)

    def _apply_incoming(self, message: TurnMessage) -> None:
        apply_incoming(self, message)

    def _ceiling_result(self) -> tuple[str, str | None]:
        return ceiling_result(self)

    def _turn_timeout(self) -> float:
        return turn_timeout(self)
