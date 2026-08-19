"""The bluff classifier: deciding how much of the thief's talk to believe.

The specification asks for the hint to enter the belief update carrying a
*reliability* coefficient, because the text may be false (ch. 6.4), and casts
the language model as a bluff classifier and behavioural profiler (ch. 6.5).
This is that. The model's only job is upstream, in `hint_claim.py`, turning a
sentence into a direction; from here on it is arithmetic.

Ch. 4.4 supplies the method. The thief says it moved north. If that were true
there would be a fresh trail in the north; the scent instead sits in the
south-east. The gap decides it -- the police concludes it is being lied to,
lowers the reliability it grants this peer's words, and keeps its mass where the
scent is.

So the scent is the arbiter and the hint is the witness:

* **A trail arrived.** Compare the claim against where that trail is strongest,
  measured from the cell the police believed the thief occupied. The profile
  learns; the belief is left alone, because the scent is about to move it anyway
  and letting the hint move it too would count one turn twice.
* **Nothing was smelled.** Now the claim is the only evidence there is, so it
  moves the belief, weighted by what this opponent's word has proved worth.

The trail is compared, not the belief's argmax: an argmax often refuses to budge
under a turn's worth of evidence, and half the lies would go unjudged.

Reliability starts at exactly one half, which makes `trust` zero and the nudge
exactly 1.0. An opponent not yet caught being honest *or* lying moves nothing at
all: the police does not guess about a stranger, it waits to find out.
"""

from dataclasses import dataclass

from police_agent.constants import Cell, Direction
from police_agent.strategy.bearings import agrees, cells_toward
from police_agent.strategy.hint_claim import claimed_direction

# How hard a fully-trusted (or fully-distrusted) claim pulls. Private tuning:
# nothing about the verbal layer is an agreed term, so this must never reach
# `peer/terms.py`.
DEFAULT_GAIN = 0.6


@dataclass(frozen=True)
class Verdict:
    """What the police made of one thing the thief said."""

    direction: Direction | None = None  # what was claimed, if anything was
    corroborated: bool | None = None  # None when the scent could not judge
    trust: float = 0.0  # -1 disbelieved .. +1 believed
    note: str = ""  # one line, for the report


class BluffAnalyst:
    """Reads the thief's hints, checks them against the scent, keeps score."""

    def __init__(self, ask=None, gain: float = DEFAULT_GAIN) -> None:
        """Track this peer's reliability score, starting from an unproven half."""
        self._ask = ask
        self._gain = gain
        self.corroborated = 0
        self.contradicted = 0

    @property
    def reliability(self) -> float:
        """How often this peer's words have survived contact with the scent.

        Laplace-smoothed, so it starts at one half rather than at whichever
        extreme the first hint happens to land on -- one corroborated claim is
        not proof of an honest opponent.
        """
        return (self.corroborated + 1) / (self.corroborated + self.contradicted + 2)

    @property
    def trust(self) -> float:
        """Reliability as a signed weight: -1 disbelieved, 0 unproven, +1 believed."""
        return 2.0 * self.reliability - 1.0

    def assess(self, hint: str, believed: Cell, smelled: Cell | None) -> Verdict:
        """Judge one hint against the trail that arrived with it."""
        direction = claimed_direction(hint, self._ask)
        if direction is None:
            return Verdict(note="no direction claimed")

        if smelled is None:
            # Nothing was smelled. The claim is all the police has, and it is
            # worth exactly what this opponent's word has been worth so far.
            return Verdict(direction, None, self.trust, f"claimed {direction}, nothing to check it")

        # A trail arrived, so it is the witness's testimony that is on trial.
        corroborated = agrees(direction, believed, smelled)
        if corroborated is None:
            return Verdict(direction, None, 0.0, f"claimed {direction}, scent inconclusive")
        self._record(corroborated)
        verb = "corroborated" if corroborated else "contradicted"
        return Verdict(
            direction,
            corroborated,
            0.0,
            f"claimed {direction}, scent {verb} it (reliability {self.reliability:.2f})",
        )

    def apply(self, verdict: Verdict, belief, origin: Cell) -> None:
        """Let a verdict move the belief, if it earned the right to."""
        if verdict.direction is None or verdict.trust == 0.0:
            return
        size = len(belief.as_matrix())
        belief.scale(
            cells_toward(origin, verdict.direction, size), 1.0 + self._gain * verdict.trust
        )

    def _record(self, corroborated: bool) -> None:
        if corroborated:
            self.corroborated += 1
        else:
            self.contradicted += 1


def resolve_bluff_analyst(config=None, gate=None, ledger=None) -> BluffAnalyst:
    """Build the analyst from this peer's private config.

    Shares `trash_talk.provider` with `strategy/talk.py`: one switch decides
    whether this peer has a local model at all. Without one the hints are still
    read, by keyword -- worse recall, no network, and the scoring is unchanged.

    It shares the rate limiter and the token ledger with the hint writer too,
    when the runtime supplies them: reading a hint and answering it are two calls
    to one server on one budget, and counting them apart would under-report both.
    """
    from police_agent.strategy.talk import DEFAULT_PROVIDER, MODEL_PROVIDERS, asker_from_config

    get = config.get if config is not None else (lambda _key, default=None: default)
    provider = str(get("trash_talk.provider") or DEFAULT_PROVIDER).lower()
    gain = float(get("bluff.gain") or DEFAULT_GAIN)
    ask = asker_from_config(get, gate, ledger) if provider in MODEL_PROVIDERS else None
    return BluffAnalyst(ask, gain)
