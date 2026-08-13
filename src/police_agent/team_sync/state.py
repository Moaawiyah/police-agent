"""The local team_sync state machine: where this series stands, and whose
sub-game is next.

`role_for_subgame` is the whole alternation rule the spec asks for (Police
owns odd sub-games, Thief owns even): both sibling processes compute it the
same way, independently, with no round trip needed to agree on it.
"""

from dataclasses import dataclass
from enum import StrEnum

from police_agent.peer.sealing import now_iso

POLICE = "police"
THIEF = "thief"


class SeriesSyncState(StrEnum):
    """Where one series' local coordination currently stands."""

    IDLE = "idle"
    WAITING = "waiting"
    READY = "ready"
    NEGOTIATING = "negotiating"
    PLAYING = "playing"
    AUDITING = "auditing"
    SETTLED = "settled"
    WAITING_FOR_SIBLING = "waiting_for_sibling"
    SERIES_COMPLETE = "series_complete"
    ERROR = "error"


def role_for_subgame(sub_game_number: int) -> str:
    """ "police" for an odd sub-game, "thief" for an even one.

    Sub-game 1 = our Police vs. the opponent's Thief, sub-game 2 = our Thief
    vs. the opponent's Police, and so on -- the alternation the six-sub-game
    match is built on.
    """
    return POLICE if sub_game_number % 2 == 1 else THIEF


# Legal forward transitions: every value in the set is a state `advance` may
# move *to* from the key. Kept explicit so an out-of-order or duplicated
# event fails loudly (`ValueError`) instead of silently overwriting progress.
_TRANSITIONS: dict[SeriesSyncState, frozenset[SeriesSyncState]] = {
    SeriesSyncState.IDLE: frozenset({SeriesSyncState.READY, SeriesSyncState.WAITING}),
    SeriesSyncState.READY: frozenset(
        {
            SeriesSyncState.NEGOTIATING,
            SeriesSyncState.WAITING_FOR_SIBLING,
            SeriesSyncState.PLAYING,
            SeriesSyncState.ERROR,
        }
    ),
    SeriesSyncState.WAITING: frozenset({SeriesSyncState.READY, SeriesSyncState.NEGOTIATING}),
    SeriesSyncState.NEGOTIATING: frozenset({SeriesSyncState.PLAYING, SeriesSyncState.ERROR}),
    SeriesSyncState.PLAYING: frozenset(
        {SeriesSyncState.AUDITING, SeriesSyncState.SETTLED, SeriesSyncState.ERROR}
    ),
    SeriesSyncState.AUDITING: frozenset({SeriesSyncState.SETTLED, SeriesSyncState.ERROR}),
    SeriesSyncState.SETTLED: frozenset(
        {
            SeriesSyncState.WAITING_FOR_SIBLING,
            SeriesSyncState.READY,
            SeriesSyncState.SERIES_COMPLETE,
        }
    ),
    SeriesSyncState.WAITING_FOR_SIBLING: frozenset(
        {SeriesSyncState.READY, SeriesSyncState.SETTLED, SeriesSyncState.ERROR}
    ),
    SeriesSyncState.SERIES_COMPLETE: frozenset(),
    SeriesSyncState.ERROR: frozenset(),
}


def can_transition(current: SeriesSyncState, target: SeriesSyncState) -> bool:
    """Whether moving from `current` to `target` is a legal step."""
    return target in _TRANSITIONS.get(current, frozenset())


@dataclass
class SeriesSyncStatus:
    """One series' local position: which sub-game, in what state, since when."""

    series_id: str
    sub_game_number: int = 1
    state: SeriesSyncState = SeriesSyncState.IDLE
    updated_at: str = ""

    def advance(
        self, target: SeriesSyncState, sub_game_number: int | None = None
    ) -> "SeriesSyncStatus":
        """A new status moved to `target`, or `ValueError` if that is not legal."""
        if not can_transition(self.state, target):
            raise ValueError(f"illegal team_sync transition: {self.state} -> {target}")
        return SeriesSyncStatus(
            series_id=self.series_id,
            sub_game_number=self.sub_game_number if sub_game_number is None else sub_game_number,
            state=target,
            updated_at=now_iso(),
        )

    def to_dict(self) -> dict:
        """This status as a plain dict, for `store.py` and the wire."""
        return {
            "series_id": self.series_id,
            "sub_game_number": self.sub_game_number,
            "state": str(self.state),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SeriesSyncStatus":
        """Rebuild a status from what `to_dict` produced (or `store.py` persisted)."""
        return cls(
            series_id=str(data["series_id"]),
            sub_game_number=int(data.get("sub_game_number", 1)),
            state=SeriesSyncState(data.get("state", SeriesSyncState.IDLE)),
            updated_at=str(data.get("updated_at", "")),
        )
