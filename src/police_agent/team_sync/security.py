"""HMAC-SHA256 defense-in-depth for team_sync's localhost coordination link.

Binding the coordinator to `127.0.0.1` (see `coordinator.py`) is the primary
defense -- nothing outside this machine can reach the tool at all. This is
the second layer the spec's security section asks for on top of that: a
message is only accepted if it was signed with the same shared secret this
process holds.

The secret is never a config value (CLAUDE.md: no hardcoded secrets, and a
private `game.toml` is a file that could be shared by accident). It comes
from the `TEAM_SYNC_SECRET` environment variable, read fresh on every call
rather than cached, so a test can set/unset it around a single check. If the
variable is unset, auth is treated as disabled -- allowed rather than a
crash -- which keeps local dev and the test suite usable without it; a real
match run must export the same value on both sibling processes.
"""

import hashlib
import hmac
import os

from police_agent.domain.crypto import canonical_json

ENV_VAR = "TEAM_SYNC_SECRET"


def secret_from_env() -> str | None:
    """The shared secret, or `None` if this process has not set one."""
    return os.environ.get(ENV_VAR) or None


def hmac_sign(secret: str, payload: bytes) -> str:
    """HMAC-SHA256 of `payload` under `secret`, as hex."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def hmac_verify(secret: str | None, payload: bytes, signature: str) -> bool:
    """Whether `signature` is a valid HMAC of `payload` under `secret`.

    Auth-disabled (`secret` falsy) always verifies: see the module docstring.
    Uses `hmac.compare_digest` so an invalid guess cannot be narrowed down by
    timing how quickly it was rejected.
    """
    if not secret:
        return True
    return hmac.compare_digest(hmac_sign(secret, payload), signature or "")


def _signable_bytes(message: dict) -> bytes:
    """The exact bytes a signature covers: every field except the signature."""
    body = {key: value for key, value in message.items() if key != "hmac"}
    return canonical_json(body).encode()


def sign_message(message: dict, secret: str | None) -> dict:
    """`message` with its `hmac` field filled in (or left empty if `secret` is unset)."""
    signature = hmac_sign(secret, _signable_bytes(message)) if secret else ""
    return {**message, "hmac": signature}


def verify_message(message: dict, secret: str | None) -> bool:
    """Whether `message`'s own `hmac` field matches its signable body."""
    if not isinstance(message, dict):
        return False
    return hmac_verify(secret, _signable_bytes(message), message.get("hmac", ""))
