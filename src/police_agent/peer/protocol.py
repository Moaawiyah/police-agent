"""The peer-to-peer wire format: what one peer is allowed to tell the other.

These dataclasses live under `peer/` and not under `domain/` on purpose. The
domain package models the game itself and must stay usable without a network;
this module exists only because two independent processes have to agree on the
shape of a JSON object (CLAUDE.md: domain logic independent of networking).

Decoding is deliberately asymmetric:

* a missing *required* field is fatal -- acting on a half-formed turn would
  corrupt the game record and the audit built from it, so it raises
  ProtocolError rather than a bare TypeError from the constructor;
* an *unknown* field is ignored -- the opponent is another team's independent
  implementation (ch. 9.4) and may carry extensions we do not model. Refusing to
  play against a superset of our own format would fail interoperability testing
  for no protocol reason.
"""

from dataclasses import MISSING, asdict, dataclass, fields

from police_agent.exceptions import ProtocolError


def _decode[T](cls: type[T], data: object) -> T:
    """Build a wire dataclass from an untrusted payload: strict, then tolerant."""
    if not isinstance(data, dict):
        raise ProtocolError(f"{cls.__name__} payload must be an object, got {type(data).__name__}")
    known = {field.name for field in fields(cls)}  # type: ignore[arg-type]
    required = {field.name for field in fields(cls) if field.default is MISSING}  # type: ignore[arg-type]
    missing = required - data.keys()
    if missing:
        raise ProtocolError(f"{cls.__name__} is missing required field(s): {sorted(missing)}")
    return cls(**{key: value for key, value in data.items() if key in known})


@dataclass
class TurnMessage:
    """One peer's public account of its turn -- and deliberately nothing more.

    The true position, the move that produced it and any capture verdict are
    absent from this message. They travel sealed inside `commit`, a SHA-256
    digest whose nonce is withheld until the end-of-game audit (specification
    ch. 5). Naming the position here would hand the opponent the single secret
    the game is played for, and would make the scent trail and the belief map
    pointless. `commit` is an opaque string at this layer: computing it, and
    re-verifying it against the revealed nonce, belongs to the commit-reveal
    step, not to the wire format.

    Receiving a TurnMessage is also what passes the turn: there is no referee
    holding a token, so the message itself is the hand-over.
    """

    step: int
    sender: str  # "police" | "thief" -- who moved, so a peer can reject its own echo
    hint: str  # free-text location cue; the specification permits it to mislead
    smell_grid: dict  # {"r,c": intensity} decaying scent, never an exact position
    commit: str  # SHA-256 over (state | move | verdict | nonce); nonce withheld
    timestamp: str  # ISO-8601 wall clock, mandatory per move for the game log
    barrier_placed: list | None = None  # police only: the cell it publicly walled
    capture_claim: list | None = None  # police only: "I claim you stand at [r, c]"
    claim_response: dict | None = None  # thief's honest {"claim": [r, c], "caught": bool}
    win_claim: dict | None = None  # thief's end-of-game {"type": "survival"}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "TurnMessage":
        return _decode(cls, data)


@dataclass
class AuditPayload:
    """The end-of-game reveal that makes the sealed commits checkable.

    Each record carries the plaintext payload, its nonce and the commit that was
    published during play, so the receiver can recompute the digest and detect a
    peer that rewrote its history after seeing how the game went (ch. 5).
    """

    sender: str
    records: list  # [{"payload": {...}, "nonce": str, "commit": str}, ...]
    result_claim: str  # "capture" | "survival" | "timeout" -- to be verified, not trusted

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "AuditPayload":
        return _decode(cls, data)


@dataclass
class ControlMessage:
    """An out-of-band signal about the *session*, never about the game record.

    This peer does not emit control messages; it only accepts them, because an
    opponent built on the reference implementation sends them best-effort and we
    would rather queue one than answer "unknown tool". Nothing here is committed
    or audited, so a control message can never influence a score.
    """

    kind: str  # "enable" | "status" | "restart" | "quit"
    sender: str
    sub_game_number: int = 1  # which sub-game of the series the signal refers to
    status: str = ""  # the sender's self-reported state, advisory only
    payload: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "ControlMessage":
        return _decode(cls, data)
