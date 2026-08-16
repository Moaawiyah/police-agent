"""Terminal conditions the police can evaluate from what it actually knows.

No referee exists, and the police never learns the thief's position during play.
That asymmetry decides what belongs here: the police can only judge conditions
about *itself* and about the clock.

The two barrier-related capture rules (Appendix He, 46 and 47 -- a barrier on
the thief's cell, and a thief left with no legal step) are deliberately absent.
Both are conditions the thief evaluates about itself and reports in a signed
response; the police cannot compute either, because it does not know where the
thief stands. What the police owes in return is *verification*: once the thief
reveals its sealed log at the end-of-game audit, every one of those answers must
be re-checked against the revealed positions. That belongs to the commit-reveal
step and operates on the opponent's revealed records, not on OwnGameState.
"""

from police_agent.domain.own_state import OwnGameState

# Outcome strings shared with the scoring table and the result JSON.
CAPTURE = "capture"
SURVIVAL = "survival"
TIMEOUT = "timeout"
TECHNICAL_LOSS = "technical_loss"

# This peer's own operator stopped the sub-game from the GUI. Not a loss the
# rules define -- nobody scores it -- but a named result so the summary and the
# audit still describe what happened, rather than a match simply going missing.
ABORTED = "aborted"

# A revealed log that does not hash to the commitments published during play:
# evidence the opponent rewrote its history.
TAMPER_FORFEIT = "tamper_forfeit"

# Outcomes that zero BOTH sides (the interop kit's binding scoring table:
# capture=(20,5), survival=(5,10), everything else=(0,0)). A zeroed sub-game
# is a sanction, not a tie -- credited to nobody, `winner_group: null`,
# `tie: false` -- so it must not fold into the tie count either. The book's
# stated reason: protocol correctness is worth more to each side than a win
# on a technicality, and an honest peer CAN be zeroed by its opponent's own
# failure (a tamper-forfeit is not a consolation prize for the honest side).
ZEROED_RESULTS = frozenset({TIMEOUT, TECHNICAL_LOSS, TAMPER_FORFEIT})


class GameRules:
    """The agreed end-of-game conditions for one sub-game.

    `max_steps` is the hard move ceiling; `survival_threshold` is how long the
    thief must last to win. The specification keeps them as separate parameters
    even though both default to the same value, so they are not merged here.
    """

    def __init__(self, max_steps: int, survival_threshold: int) -> None:
        """The agreed step ceiling and survival threshold for one sub-game."""
        self.max_steps = max_steps
        self.survival_threshold = survival_threshold

    def out_of_steps(self, state: OwnGameState) -> bool:
        """True once the sub-game's hard move ceiling has been reached."""
        return state.step_number >= self.max_steps

    def thief_survived(self, step_number: int) -> bool:
        """Whether a survival claim at `step_number` is consistent with the terms.

        The thief raises the claim; the police checks it against the agreed
        threshold rather than trusting the claim on its face.
        """
        return step_number >= self.survival_threshold
