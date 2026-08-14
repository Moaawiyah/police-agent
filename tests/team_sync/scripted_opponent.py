"""The third-party opponent for a team_sync series test, scripted at the wire.

Not our thief repository and not an in-process thief (CLAUDE.md ch. 2.4.2):
it seals its own turns with `CommitReveal` and reveals them honestly at the
audit, which is the minimum an opponent must do for a sub-game to settle as
anything other than a technical win. Every sub-game in the series is played
against this, including the ones the sibling thief_agent process owns.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.domain.rules import CAPTURE, SURVIVAL
from police_agent.peer.protocol import AuditPayload
from tests.peer.fake_transport import FakeTransport, thief_turn
from tests.team_sync.helpers import OPPONENT

THIEF_POSITION = [3, 3]


def sealed_turn(step: int) -> dict:
    """One thief turn record, committed the way the protocol requires."""
    payload = {"step": step, "position": THIEF_POSITION, "move": "HOLD:-", "barrier": None}
    return {"payload": payload, **CommitReveal.seal(payload)}


class ScriptedOpponent(FakeTransport):
    """An opponent that answers every turn and reveals a log that verifies.

    Stateful rather than a fixed script, because one transport is held across
    the whole series: the step counter and the sealed records reset at each
    audit exchange, which is exactly where one sub-game ends and the next
    peer's fresh runtime begins.
    """

    def __init__(self, result_claim: str = SURVIVAL) -> None:
        """An opponent claiming `result_claim` at every audit it does not lose."""
        super().__init__()
        self._result_claim = result_claim
        self._sealed: list[dict] = []
        self._step = 0
        self._caught = False
        self._turns_before = 0  # police turns already sent when this sub-game opened

    def exchange_agreement(self, signed: dict) -> dict:
        """Agree to exactly our terms, under the opponent group's identity.

        `FakeTransport` echoes our own identity back, which would file
        Police's own sub-games under `OURTEAM-vs-OURTEAM` while the imported
        ones land under `OURTEAM-vs-THEIRTEAM` -- two series where the match
        has one.
        """
        return {**super().exchange_agreement(signed), "identity": dict(OPPONENT)}

    def poll_turn(self, timeout: float) -> dict:
        """The next sealed turn, produced on demand rather than pre-scripted."""
        self._step += 1
        sealed = sealed_turn(self._step)
        self._sealed.append(sealed)
        return thief_turn(self._step, commit=sealed["commit"], claim_response=self._answer_claim())

    def _answer_claim(self) -> dict | None:
        """Answer an outstanding capture claim honestly.

        Honestly matters: `domain/semantic_moves.py:79` re-derives the answer
        from the revealed position, so a thief that concedes a capture it did
        not suffer forfeits the sub-game for tampering. This one never moves,
        so the claim is true exactly when it names `THIEF_POSITION`.

        Only claims made *this* sub-game count: `sent_turns` is one list for
        the whole series, and answering the previous sub-game's last claim is
        an answer to a claim this one never made -- itself a forfeit.
        """
        if len(self.sent_turns) <= self._turns_before:
            return None
        claim = self.sent_turns[-1].get("capture_claim")
        if not claim:
            return None
        caught = list(claim) == THIEF_POSITION
        self._caught = self._caught or caught
        return {"claim": claim, "caught": caught}

    def exchange_audit(self, payload: dict) -> dict:
        """Reveal every record sealed this sub-game, then start the next one clean."""
        self.sent_audits.append(payload)
        records, self._sealed = self._sealed, []
        claim = CAPTURE if self._caught else self._result_claim
        self._step, self._caught = 0, False
        self._turns_before = len(self.sent_turns)
        return AuditPayload(sender="thief", records=records, result_claim=claim).to_dict()
