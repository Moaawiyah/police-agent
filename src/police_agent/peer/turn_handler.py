"""Folding an opponent's message into what this peer knows.

Everything the police ever learns about the thief passes through here: a scent
grid, a free-text hint, and the thief's answers to claims. There is no shared
board to consult and no referee to ask, so if it did not arrive in a message,
the police does not know it.

The thief's claims are checked, not believed. A survival claim is tested against
the agreed threshold before it is allowed to end the game, because the peer
making the claim is the peer that benefits from it. What cannot be checked here
is checked at the audit, once the sealed positions are revealed.
"""

from dataclasses import dataclass, field

from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import GameRules
from police_agent.peer.protocol import TurnMessage
from police_agent.strategy.threat import ThreatEstimate


@dataclass
class IncomingOutcome:
    """What an incoming message means for the game, if anything."""

    i_won: bool = False  # the thief confirmed my capture claim
    opponent_won: bool = False  # the thief claimed survival and it checks out
    disputes: list[str] = field(default_factory=list)  # claims that failed my check


class TurnHandler:
    """Applies the thief's messages to the police's own view of the game."""

    def __init__(self, state: OwnGameState, threat: ThreatEstimate, rules: GameRules) -> None:
        self.state = state
        self.threat = threat
        self.rules = rules
        self.history: list[dict] = []  # every message received, for replay and the report

    def process(self, message: TurnMessage) -> IncomingOutcome:
        self.history.append(message.to_dict())
        if message.barrier_placed:
            # Barriers are a police-only mechanic (3.4), so this should not arrive
            # from a thief. It is honoured rather than rejected: a declared barrier
            # is impassable for both sides, and refusing to record one could only
            # ever hurt this peer by letting it plan a route through a wall.
            self.state.note_barrier(tuple(message.barrier_placed))
        # One step of the belief filter, and the order is the substance of it:
        # the message is proof the thief moved, so the belief spreads *before*
        # the scent that arrived with it is allowed to sharpen it again.
        self.threat.diffuse()
        self.threat.observe_smell(message.smell_grid)

        outcome = IncomingOutcome()
        if message.claim_response and message.claim_response.get("caught"):
            outcome.i_won = True
        if message.win_claim:
            self._check_survival(message, outcome)
        return outcome

    def _check_survival(self, message: TurnMessage, outcome: IncomingOutcome) -> None:
        """Allow a survival claim only when the agreed threshold has been reached.

        A thief that claims survival early is not conceded to; the game carries
        on and the dispute is recorded for the report. The audit is where it is
        settled, since only the revealed log proves how many steps really passed.
        """
        claim_type = message.win_claim.get("type")
        if claim_type != "survival":
            outcome.disputes.append(f"unknown win claim {claim_type!r} at step {message.step}")
            return
        if self.rules.thief_survived(message.step):
            outcome.opponent_won = True
        else:
            outcome.disputes.append(
                f"survival claimed at step {message.step}, "
                f"threshold is {self.rules.survival_threshold}"
            )
