"""The team_sync wire schema: small control envelopes, plus the canonical
`SettledSubgameResult` shape a settled sub-game is normalized into.

This is the contract the sibling Thief repository implements independently
(CLAUDE.md: two separate repos, no shared module) -- every field name and
the `result_hash` derivation here must match that repo's copy byte for byte,
since neither side can import the other's definitions.

Every envelope carries `schema_version`, `type`, `series_id`, a unique
`message_id` and an `hmac` field (`security.py` fills the last one in).

The `SettledSubgameResult` schema itself -- the big, mostly-nested payload a
settled sub-game is normalized into -- is defined and validated in
`import_adapter.py`, which is its only reader in this repo; only its wire
`type` string (`SUBGAME_RESULT`) lives here, alongside the smaller control
envelopes both sides actually construct.
"""

import uuid
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = 1

SERIES_START = "series_start"
HANDOFF = "handoff"
STATUS_REQUEST = "status_request"
STATUS_RESPONSE = "status_response"
ACK = "ack"
SUBGAME_RESULT = "subgame_result"
SERIES_COMPLETE = "series_complete"


def new_message_id() -> str:
    """A fresh unique id for one outbound message."""
    return uuid.uuid4().hex


class _Envelope:
    """Shared `to_dict`: any dataclass subclass serializes the same way."""

    def to_dict(self) -> dict:
        """This message as a plain dict, ready for the wire."""
        return asdict(self)


@dataclass
class SeriesStart(_Envelope):
    """Police (the series owner) announces a new series to the sibling Thief.

    `sub_game_number` is the first sub-game this unlocks for the recipient
    (the sibling's own team_sync copy keys its `wait_for_unlock` on this
    exact field name -- see `messages.py`'s module docstring on wire parity).
    """

    series_id: str
    game_id: str
    num_sub_games: int
    sub_game_number: int
    sender_role: str
    start_role: str = "police"
    next_role: str = "thief"
    status: str = "settled"
    message_id: str = field(default_factory=new_message_id)
    schema_version: int = SCHEMA_VERSION
    type: str = SERIES_START
    hmac: str = ""


@dataclass
class SubgameHandoff(_Envelope):
    """Sub-game `completed_subgame` is settled; `next_subgame` is unlocked.

    `sub_game_number` duplicates `next_subgame`'s value under the field name
    the sibling's `wait_for_unlock` actually matches on -- kept alongside the
    more descriptive `completed_subgame`/`next_subgame` pair this repo's own
    tests already assert on, rather than renaming either.
    """

    series_id: str
    completed_subgame: int
    next_subgame: int
    sub_game_number: int
    sender_role: str
    start_role: str = "police"
    next_role: str = "thief"
    status: str = "settled"
    message_id: str = field(default_factory=new_message_id)
    schema_version: int = SCHEMA_VERSION
    type: str = HANDOFF
    hmac: str = ""


@dataclass
class StatusRequest(_Envelope):
    """A late-starting (or restarted) sibling asking where the series stands."""

    series_id: str
    sender_role: str
    message_id: str = field(default_factory=new_message_id)
    schema_version: int = SCHEMA_VERSION
    type: str = STATUS_REQUEST
    hmac: str = ""


@dataclass
class StatusResponse(_Envelope):
    """The answer to a `StatusRequest`: this peer's own current position."""

    series_id: str
    state: str
    current_subgame: int
    sender_role: str
    message_id: str = field(default_factory=new_message_id)
    schema_version: int = SCHEMA_VERSION
    type: str = STATUS_RESPONSE
    hmac: str = ""


@dataclass
class Ack(_Envelope):
    """Best-effort acknowledgement of one earlier message, by its id."""

    series_id: str
    ack_for_message_id: str
    sub_game_number: int
    sender_role: str
    message_id: str = field(default_factory=new_message_id)
    schema_version: int = SCHEMA_VERSION
    type: str = ACK
    hmac: str = ""
