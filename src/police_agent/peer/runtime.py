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
"""

import time

from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import (
    ABORTED,
    CAPTURE,
    SURVIVAL,
    TECHNICAL_LOSS,
    TIMEOUT,
    GameRules,
)
from police_agent.domain.scent import ScentField
from police_agent.peer.controls import GameControls
from police_agent.peer.handshake import identity_from_config, negotiate
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.sealing import now_iso
from police_agent.peer.step_zero import sealed_step_zero
from police_agent.peer.summary import build_summary, exchange_and_audit
from police_agent.peer.terms import validate_agreement
from police_agent.peer.turn_handler import TurnHandler
from police_agent.peer.turn_sender import take_turn
from police_agent.peer.view import snapshot
from police_agent.shared.gatekeeper import Gatekeeper
from police_agent.shared.rate_limit import DosDetector
from police_agent.shared.tokens import TokenLedger
from police_agent.strategy import resolve_brain
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.bluff import resolve_bluff_analyst
from police_agent.strategy.talk import resolve_hint_writer


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
    ) -> None:
        # Validated before anything else: a missing agreed term is far cheaper to
        # discover here than three turns into a match against another group.
        self.terms = validate_agreement(config)
        self.config = config
        self.transport = transport

        size = self.terms["board_size"]
        self.state = OwnGameState(tuple(self.terms["cop_start"]), size)
        # The survival threshold is deliberately not a signed term: the reference
        # does not sign it, and matching its term list exactly is what lets the
        # handshake succeed against anyone who followed it. It still comes from
        # the shared, byte-identical game.json, so both peers agree. `require`
        # makes a missing one a config error rather than a crash mid-match.
        self.rules = GameRules(self.terms["max_steps"], config.require("rules.survival_threshold"))
        self.barriers_max = self.terms["barriers_max"]

        # One gate and one ledger for the whole match. Every outbound call to
        # somebody else's service leaves through the gate (Appendix He 28) and
        # every model call this peer makes lands in the tally (Appendix He 54);
        # building them here is what stops the two halves of the verbal layer
        # from quietly running two rate limiters at twice the agreed rate.
        self.gatekeeper = Gatekeeper.from_config(config)
        self.tokens = TokenLedger()
        # The inbound flood line, phrased as "fast enough to fill the gate's
        # whole waiting line inside one second" so that it moves with the agreed
        # queue depth rather than being a number somebody picked: at the shipped
        # 100 it is 100 messages a second. A legal turn costs an HTTP round trip
        # plus the opponent's own thinking, so a real match sits two orders of
        # magnitude below it -- which is the point. This reading must never be
        # able to accuse an honest peer.
        self.inbound_dos = DosDetector(self.gatekeeper.limits.queue_depth * 60.0)

        self.threat = threat or BeliefGrid.from_config(self.terms, config)
        self.brain = brain or resolve_brain(config)
        self.scent = scent or ScentField.from_terms(self.terms)
        self.hint_writer = hint_writer or resolve_hint_writer(
            config, gate=self.gatekeeper, ledger=self.tokens
        )
        self.analyst = analyst or resolve_bluff_analyst(config, self.gatekeeper, self.tokens)
        self.handler = TurnHandler(self.state, self.threat, self.rules, self.analyst)

        self._listener = listener
        self.controls = controls or GameControls()
        # The declaration heads the log, sealed before anything is played, so its
        # digest can go out with the handshake below (Appendix He 24/53).
        self.records: list[dict] = [sealed_step_zero(config)]
        self.disputes: list[str] = []
        self.peer_identity: dict = {}
        self.started_at = now_iso()
        self.started_monotonic = time.monotonic()
        self._result: tuple[str, str | None] | None = None

    def notify(self, event: dict) -> None:
        """Publish a progress event, carrying what the board looked like at the time.

        The snapshot is taken here, on the game thread, because a watcher that
        read the runtime later would read a board that had already moved on. It
        is skipped entirely when nobody is listening: the headless agent copies
        no sets and builds no belief matrix it will never draw.
        """
        if self._listener is None:
            return
        self._listener({**event, "view": snapshot(self)})

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

        self._turn_loop()
        result, winner = self._result
        result, winner, audit = exchange_and_audit(self, result, winner)
        summary = build_summary(self, result, winner, audit)
        self.notify({"type": "game_over", "summary": summary})
        return summary

    def _turn_loop(self) -> None:
        timeout = self._turn_timeout()
        while self._result is None:
            # Checked at the turn boundary, never mid-turn: a pause that landed
            # between sealing a move and sending it would leave this peer having
            # committed to something the opponent never received.
            self.controls.wait_if_paused()
            if self.controls.stopped:
                self._result = (ABORTED, None)
                return
            incoming = self.transport.poll_turn(timeout)
            if incoming is None:
                # Silence past the agreed watchdog. The specification treats an
                # unresponsive peer as forfeiting rather than drawing, so this is
                # a technical loss for the thief and not a timeout of the game.
                self._result = (TECHNICAL_LOSS, "police")
                return
            # Measured, never acted on. Appendix He 29 wants a DOS detector on
            # the network resources, and this is where every inbound message
            # can be counted -- but dropping or delaying a turn to defend
            # ourselves would forfeit the match to the very peer we suspected.
            # So the reading goes in the summary and the status line, and the
            # turn is played. The gate that can actually refuse traffic is the
            # outbound one, where the cost of being wrong is a missing taunt.
            self.inbound_dos.record()
            self._apply_incoming(TurnMessage.from_dict(incoming))

    def _apply_incoming(self, message: TurnMessage) -> None:
        outcome = self.handler.process(message)
        self.disputes.extend(outcome.disputes)
        if outcome.replayed:
            # Not a turn, so it does not earn one back. Keep waiting: a peer that
            # only ever repeats itself goes silent by the watchdog instead, and a
            # duplicate is as likely to be the transport's retry as an attack.
            self.notify({"type": "replay_ignored", "step": message.step})
            return
        self.notify({"type": "incoming", "step": message.step, "hint": message.hint})

        if outcome.i_won:
            self._result = (CAPTURE, "police")
        elif outcome.opponent_won:
            self._result = (SURVIVAL, "thief")
        elif self.rules.out_of_steps(self.state):
            self._result = self._ceiling_result()
        else:
            take_turn(self)

    def _ceiling_result(self) -> tuple[str, str | None]:
        """What it means to run out of moves without a capture.

        The two limits are separate parameters even though they usually coincide:
        reaching the move ceiling only hands the thief a win if it also lasted
        the agreed survival threshold. Otherwise the sub-game simply expired.
        """
        if self.rules.thief_survived(self.state.step_number):
            return (SURVIVAL, "thief")
        return (TIMEOUT, None)

    def _turn_timeout(self) -> float:
        """How long to wait for the thief, preferring this peer's private setting."""
        return float(
            self.config.get("network.turn_timeout_seconds")
            or self.config.get("network.watchdog_timeout_seconds")
            or 60.0
        )
