"""The two per-sub-game artifacts: what was agreed, and what then happened.

Ch. 9.3.3's middle pair. The config file states the physics and the scoring the
two groups signed up to, hashed so the pair can be compared without reading it;
the log file is the step-by-step record that lets the replay simulator (ch. 7)
re-verify every commitment. One of each per sub-game, both named `<role>_<game_id>_g<NN>.json`.

Neither is written by the game -- both are projections of the match record
`peer/summary.py` already produced, which is what keeps the schema (an agreement
with another team's parser) out of the rules (which are ours).

## `config_sha256` is over the agreed file, not over the handshake subset

`peer/terms.py` verifies a must-match *subset* on the wire, because a term the
opponent's build does not know about would fail every handshake. The artifact
hashes the whole agreed `game.json` instead: ch. 9.2 says that file is loaded
byte-identically on both sides precisely so it can be hashed consistently, and
the lecturer comparing two teams' config artifacts is comparing files, not
handshakes. When the agreed file is not to hand the verified terms stand in --
degraded, but never absent, because a missing hash reads as a missing agreement.

## `mutual_agreement` here is deliberately asymmetric

The log's digest is taken over *our own* sealed records, so the two peers'
values necessarily differ and only `confirmed` is comparable between them. This
looks like a bug and it is not: the log is one peer's testimony, and a digest
that matched the opponent's would mean we had hashed something other than what
we are testifying to. The symmetric digest -- the one both sides must land on --
lives in the result artifact, over the agreed outcome.
"""

from police_agent.constants import Role
from police_agent.peer.step_zero import is_step_zero, turn_records
from police_agent.report.ids import SCHEMA_VERSION, canonical_sha256, consensus_signature

CONFIG_TYPE = "agreed_config"
LOG_TYPE = "sub_game_log"

CONFIG_NOTE = (
    "The agreed configuration for ONE sub-game: every quantitative parameter of "
    "the game (Appendix Vav), loaded byte-identically by both peers and hashed "
    "into config_sha256 so the two copies can be compared without reading them. "
    "Defines the physics and the scoring both groups agreed to; it decides "
    "nothing that happened, which is the log's and the result's job."
)

LOG_NOTE = (
    "The step-by-step record of ONE sub-game: the step-zero declaration, then "
    "every commit-reveal commitment with its payload, nonce and hash, plus what "
    "was made of the opponent's hints. Its role is to let the replay simulator "
    "(ch. 7) re-verify the whole match cryptographically. mutual_agreement here "
    "covers THIS peer's records, so the two peers' sha256 values differ by "
    "design and only 'confirmed' is comparable between them."
)

AGREEMENT_REMARK = (
    "Asymmetric on purpose: sha256 is over this peer's own sealed records. The "
    "symmetric digest both peers must agree on is in the result artifact."
)


def build_config(facts, summary: dict, config=None) -> dict:
    """The agreed terms for this sub-game, with the digest that pins them."""
    agreed = _agreed_terms(summary, config)
    return {
        "_schema": CONFIG_NOTE,
        "schema_version": SCHEMA_VERSION,
        "artifact_type": CONFIG_TYPE,
        "game_id": facts.game_id,
        "game_uid": facts.game_uid,
        "links": facts.links,
        "sub_game_number": facts.sub_game_number,
        "timezone": facts.timezone,
        "agreed_between": facts.groups,
        "config": agreed,
        "config_sha256": canonical_sha256(agreed),
    }


def build_log(facts, summary: dict) -> dict:
    """This sub-game as it was played, sealed record by sealed record."""
    records = summary.get("records") or []
    audit = summary.get("audit") or {}
    return {
        "_schema": LOG_NOTE,
        "schema_version": SCHEMA_VERSION,
        "artifact_type": LOG_TYPE,
        "game_id": facts.game_id,
        "game_uid": facts.game_uid,
        "links": facts.links,
        "sub_game_number": facts.sub_game_number,
        "timezone": facts.timezone,
        "roles": roles_of(summary),
        "started_at": facts.started_at,
        "ended_at": facts.ended_at,
        "duration_seconds": summary.get("duration_seconds", 0),
        "result": summary.get("result", ""),
        "winner": summary.get("winner"),
        # None on any ordinary result; set only when the loop watchdog (ch.
        # 8.4.2) itself stopped this sub-game -- the only place that reason
        # survives the process, since it is peer-local and never crosses the
        # wire to the opponent.
        "abort_reason": summary.get("abort_reason"),
        "steps": summary.get("steps", 0),
        # The declaration is carried whole rather than as its payload: a verifier
        # needs the nonce and the commit to redo the seal the opponent was handed
        # at the handshake, and a payload alone would only be a claim about it.
        "step_zero": _declaration_record(records),
        "records": turn_records(records),
        "opponent_messages": summary.get("history") or [],
        "hint_readings": summary.get("hint_readings") or [],
        "opponent_reliability": summary.get("opponent_reliability"),
        "disputes": summary.get("disputes") or [],
        "tokens": summary.get("tokens") or {},
        "gatekeeper": summary.get("gatekeeper") or {},
        "audit": audit,
        "mutual_agreement": {
            "_remark": AGREEMENT_REMARK,
            "confirmed": bool(audit.get("passed")),
            "sha256": consensus_signature({"records": records}),
        },
    }


def roles_of(summary: dict) -> dict:
    """Which group played which side this sub-game.

    Read from the record rather than assumed, because roles alternate across the
    series (ch. 9.3.3) and this peer is only the police in the games where it is.
    """
    identity = summary.get("identity") or {}
    peer = summary.get("peer_identity") or {}
    mine = str(summary.get("role") or Role.POLICE)
    theirs = Role.THIEF if mine == Role.POLICE else Role.POLICE
    return {mine: identity.get("group_id", ""), str(theirs): peer.get("group_id", "")}


def _agreed_terms(summary: dict, config) -> dict:
    """The agreed `game.json`, or the verified handshake subset in its absence."""
    shared = getattr(config, "shared", None) if config is not None else None
    return shared or summary.get("terms") or {}


def _declaration_record(records: list) -> dict:
    """The sealed step-zero record, or `{}` for a log written without one."""
    for record in records:
        if is_step_zero(record):
            return record
    return {}
