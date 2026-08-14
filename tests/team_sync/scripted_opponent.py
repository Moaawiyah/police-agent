"""The third-party opponent for a team_sync series test, scripted at the wire.

Not our thief repository and not an in-process thief (CLAUDE.md ch. 2.4.2):
it seals its own turns with `CommitReveal` and reveals them honestly at the
audit, which is the minimum an opponent must do for a sub-game to settle as
anything other than a technical win. Every sub-game in the series is played
against this, including the ones the sibling thief_agent process owns.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.domain.rules import SURVIVAL
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
        """An opponent that will claim `result_claim` at every audit."""
        super().__init__()
        self._result_claim = result_claim
        self._sealed: list[dict] = []
        self._step = 0

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
        return thief_turn(self._step, commit=sealed["commit"])

    def exchange_audit(self, payload: dict) -> dict:
        """Reveal every record sealed this sub-game, then start the next one clean."""
        self.sent_audits.append(payload)
        records, self._sealed = self._sealed, []
        self._step = 0
        return AuditPayload(
            sender="thief", records=records, result_claim=self._result_claim
        ).to_dict()
