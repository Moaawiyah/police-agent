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
from police_agent.domain.rules import CAPTURE, SURVIVAL, TECHNICAL_LOSS, TIMEOUT, GameRules
from police_agent.domain.scent import ScentField
from police_agent.peer.handshake import identity_from_config, negotiate
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.sealing import now_iso
from police_agent.peer.summary import build_summary, exchange_and_audit
from police_agent.peer.terms import validate_agreement
from police_agent.peer.turn_handler import TurnHandler
from police_agent.peer.turn_sender import take_turn
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

        self.threat = threat or BeliefGrid.from_config(self.terms, config)
        self.brain = brain or resolve_brain(config)
        self.scent = scent or ScentField.from_terms(self.terms)
        self.hint_writer = hint_writer or resolve_hint_writer(config)
        self.analyst = analyst or resolve_bluff_analyst(config)
        self.handler = TurnHandler(self.state, self.threat, self.rules, self.analyst)

        self._listener = listener or (lambda event: None)
        self.records: list[dict] = []
        self.disputes: list[str] = []
        self.peer_identity: dict = {}
        self.started_at = now_iso()
        self.started_monotonic = time.monotonic()
        self._result: tuple[str, str | None] | None = None

    def notify(self, event: dict) -> None:
        """Publish a progress event. The GUI subscribes here; nothing else needs to."""
        self._listener(event)

    def run(self) -> dict:
        """Play one sub-game to a result and return the match summary."""
        self.peer_identity = negotiate(
            self.terms, identity_from_config(self.config), self.transport
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
            incoming = self.transport.poll_turn(timeout)
            if incoming is None:
                # Silence past the agreed watchdog. The specification treats an
                # unresponsive peer as forfeiting rather than drawing, so this is
                # a technical loss for the thief and not a timeout of the game.
                self._result = (TECHNICAL_LOSS, "police")
                return
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
        self.notify({"type": "incoming", "step": message.step})

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
