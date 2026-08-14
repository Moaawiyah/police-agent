"""Validating a `SettledSubgameResult` before `import_adapter.py` files it,
split out to keep that file under the project's line budget.

Re-exported from `import_adapter.py` so existing
`from police_agent.team_sync.import_adapter import compute_result_hash` (and
`import_adapter.compute_result_hash` / `.validate_settled_result` /
`.idempotency_key`) callers keep working unchanged.
"""

import hashlib

from police_agent.domain.crypto import canonical_json
from police_agent.exceptions import CryptoError, ProtocolError
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
