"""Importing a settled Thief sub-game into this Police process's own report
pipeline, so the binding series result covers every sub-game regardless of
which of our two sibling processes actually played it.

The trick: normalize the `SettledSubgameResult` into the shape
`peer/summary.py::build_summary()` already produces, then call the SDK's own
`write_artifacts()` on it, exactly as Police does for its own sub-games.
`report/writer.py` already rebuilds the series result from every sibling
`record_*.json` file regardless of who wrote it, so nothing downstream needs
to know this one came from across a socket.
"""

import hashlib
import json
from pathlib import Path

from police_agent.domain.crypto import canonical_json
from police_agent.exceptions import CryptoError, ProtocolError
from police_agent.peer.series import series_count
from police_agent.report.facts import facts_from
from police_agent.report.writer import series_records
from police_agent.team_sync.messages import SUBGAME_RESULT

# Keys the hash excludes (must match the sibling Thief repo's independently
# implemented `export_adapter.py` byte for byte). `message_id` is excluded
# alongside `hmac`/`result_hash` because it is a fresh random nonce on every
# send: keeping it in the hash would make a retried delivery of the exact
# same settled outcome hash differently each time, breaking the
# `series_id + sub_game_number + sender_role + result_hash` idempotency key.
RESULT_HASH_EXCLUDED = ("hmac", "result_hash", "message_id")
_KEY_FIELDS = ("series_id", "sub_game_number", "sender_role", "result_hash")

# The minimum a `SettledSubgameResult` must carry before this peer files it.
REQUIRED_RESULT_FIELDS = (
    "schema_version",
    "type",
    "series_id",
    "message_id",
    "game_id",
    "sub_game_number",
    "sender_role",
    "status",
    "result",
    "winner",
    "identity",
    "peer_identity",
    "records",
    "result_hash",
)


def compute_result_hash(payload: dict) -> str:
    """SHA-256 over the settled result, minus its own hash and signature."""
    body = {key: value for key, value in payload.items() if key not in RESULT_HASH_EXCLUDED}
    return hashlib.sha256(canonical_json(body).encode()).hexdigest()


def idempotency_key(payload: dict) -> str:
    """`series_id + sub_game_number + sender_role + result_hash`."""
    return "|".join(str(payload.get(name, "")) for name in _KEY_FIELDS)


def validate_settled_result(payload: dict) -> None:
    """Raise unless `payload` is a well-formed, un-tampered `SettledSubgameResult`."""
    if not isinstance(payload, dict):
        raise ProtocolError("SettledSubgameResult payload must be an object")
    missing = [name for name in REQUIRED_RESULT_FIELDS if name not in payload]
    if missing:
        raise ProtocolError(f"SettledSubgameResult is missing field(s): {missing}")
    if payload.get("type") != SUBGAME_RESULT:
        raise ProtocolError(f"expected a {SUBGAME_RESULT!r} message, got {payload.get('type')!r}")
    recomputed = compute_result_hash(payload)
    if payload.get("result_hash") != recomputed:
        raise CryptoError("SettledSubgameResult.result_hash does not match its own content")


def to_summary(payload: dict) -> dict:
    """The exact shape `build_summary()` produces, from a settled Thief
    sub-game rather than a runtime this process ran itself.

    `role` is always "thief": this only ever imports sub-games the *sibling*
    process played. No `belief_log` key -- it is a police-only concept.
    """
    return {
        "result": payload.get("result", ""),
        "winner": payload.get("winner"),
        "abort_reason": payload.get("abort_reason"),
        "role": "thief",
        "steps": payload.get("steps", 0),
        "unique_cells": payload.get("unique_cells", 0),
        "barriers_used": payload.get("barriers_used", 0),
        "started_at": payload.get("started_at", ""),
        "ended_at": payload.get("ended_at", ""),
        "duration_seconds": payload.get("duration_seconds", 0),
        "group_name": (payload.get("identity") or {}).get("group_name", "unnamed"),
        "peer_identity": payload.get("peer_identity") or {},
        "terms": payload.get("terms") or {},
        "identity": payload.get("identity") or {},
        "step_zero": payload.get("step_zero") or {},
        "audit": payload.get("audit") or {},
        "opponent_reliability": payload.get("opponent_reliability"),
        "tokens": payload.get("tokens") or {},
        "gatekeeper": payload.get("gatekeeper") or {},
        "inbound_dos": payload.get("inbound_dos") or {},
        "hint_readings": payload.get("hint_readings") or [],
        "disputes": payload.get("disputes") or [],
        "records": payload.get("records") or [],
        "opponent_records": payload.get("opponent_records") or [],
        "history": payload.get("history") or [],
        "my_log": payload.get("my_log") or [],
    }


def import_and_persist(payload: dict, agent, base, store) -> dict:
    """Validate, dedupe, normalize and file a settled Thief sub-game.

    A payload already seen (same idempotency key) is filed exactly once: a
    retried delivery returns the same normalized summary without writing or
    emailing a second time.
    """
    validate_settled_result(payload)
    summary = to_summary(payload)
    key = idempotency_key(payload)
    if store.seen(key):
        return summary
    paths = agent.write_artifacts(summary, base)
    store.mark_seen(key)
    maybe_email_final_report(agent, paths, summary, store)
    return summary


def maybe_email_final_report(agent, paths: dict, summary: dict, store) -> bool:
    """Send the binding report exactly once, once every sub-game is on file.

    Public: `scheduler.py` calls this after Police's own odd sub-game write
    too, since a 1/3/5-sub-game series ends on Police's own, not an import.
    The gate is "every sub-game has a terminal artifact", never "every audit
    passed" (a tamper-forfeit must still be reported). Returns whether this
    call is the one that sent it.
    """
    directory = Path(paths["result"]).parent
    facts = facts_from(summary, agent.config)
    filed = series_records(directory, facts.game_id)
    have = {int((record.get("step_zero") or {}).get("sub_game_number", 0)) for record in filed}
    needed = set(range(1, series_count(agent.config) + 1))
    if not needed.issubset(have):
        return False
    result_json = json.loads(Path(paths["result"]).read_text(encoding="utf-8"))
    report_hash = str((result_json.get("mutual_agreement") or {}).get("sha256", ""))
    if store.email_sent(facts.game_id, report_hash):
        return False
    agent.email_report(paths)
    store.mark_email_sent(facts.game_id, report_hash)
    return True
