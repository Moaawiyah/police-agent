"""Reference-v3 wire, sealing, and audit helpers.

The reference peer keeps the MCP tool names close to Police's protocol, but its
commitment bytes are different and its turn validator is deliberately strict.
This module isolates that dialect so the established native protocol remains
available to unit fakes and older Police peers while the SDK can opt into the
reference wire explicitly.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any

from police_agent.exceptions import CryptoError

HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
SENDERS = {"police", "thief"}
OPTIONAL = ("barrier_placed", "capture_claim", "claim_response", "win_claim")
NONCE_BYTES = 16


def canonical_json(payload: Any) -> str:
    """The reference's compact, sorted JSON representation."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def new_nonce() -> str:
    return secrets.token_hex(NONCE_BYTES)


def commit_of(payload: dict[str, Any], nonce: str) -> str:
    """Hash the payload *with* the nonce inserted as a JSON field.

    This is intentionally not ``sha256(canonical(payload) + '|' + nonce)``;
    that is the native Police format and is the reason the two old logs could
    not be replayed against one another.
    """
    sealed = dict(payload)
    sealed["nonce"] = nonce
    return hashlib.sha256(canonical_json(sealed).encode("utf-8")).hexdigest()


def seal(payload: dict[str, Any], nonce: str | None = None) -> dict[str, str]:
    nonce = nonce or new_nonce()
    return {"nonce": nonce, "commit": commit_of(payload, nonce)}


def verify(payload: dict[str, Any], nonce: str, announced: str) -> None:
    if (
        not isinstance(payload, dict)
        or not isinstance(nonce, str)
        or not isinstance(announced, str)
    ):
        raise CryptoError("Reference-v3 commit reveal is malformed")
    recomputed = commit_of(payload, nonce)
    if not secrets.compare_digest(recomputed, announced):
        raise CryptoError(
            f"Reference-v3 commit mismatch: published {announced[:16]}..., "
            f"recomputed {recomputed[:16]}..."
        )


def refuse_turn(message: Any) -> str:
    """Return the reference validator's reason, or ``""`` when accepted."""
    if not isinstance(message, dict):
        return "message: required object"
    step = message.get("step")
    if not isinstance(step, int) or isinstance(step, bool) or step < 0:
        return "step: required non-negative int"
    if message.get("sender") not in SENDERS:
        return "sender: required 'police' or 'thief'"
    if not isinstance(message.get("hint", ""), str):
        return "hint: required str"
    grid = message.get("smell_grid")
    if not isinstance(grid, dict) or not _grid_is_numeric(grid):
        return "smell_grid: required dict of 'r,c' -> number"
    commit = message.get("commit")
    if not isinstance(commit, str) or not HEX64.match(commit):
        return "commit: required 64-char lowercase hex"
    timestamp = message.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        return "timestamp: required non-empty str"
    return ""


def _grid_is_numeric(grid: dict[Any, Any]) -> bool:
    return all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in grid.values()
    )


def from_internal(turn: dict[str, Any], timestamp: str) -> dict[str, Any]:
    """Translate a Police turn dict to the reference-v3 wire spelling."""
    sender = str(turn.get("sender", "")).lower()
    message: dict[str, Any] = {
        "step": int(turn.get("step", 0) or 0),
        "sender": sender if sender in SENDERS else "police",
        "hint": str(turn.get("hint") or ""),
        "smell_grid": {
            str(key): float(value) for key, value in (turn.get("smell_grid") or {}).items()
        },
        "commit": str(turn.get("commit") or ""),
        "timestamp": timestamp,
    }
    for name in OPTIONAL:
        message[name] = turn.get(name)
    return message


def audit_from_records(
    sender: str, records: list[dict[str, Any]], result_claim: str
) -> dict[str, Any]:
    role = str(sender).lower()
    return {
        "sender": role if role in SENDERS else "police",
        "records": list(records),
        "result_claim": str(result_claim),
    }


def police_step_payload(state, hint: str) -> dict[str, Any]:
    """Build the exact reference StepIntent payload for a completed Police turn."""
    last = state.log[-1] if state.log else {}
    barrier = last.get("barrier")
    move = (
        f"BARRIER:{int(barrier[0])},{int(barrier[1])}"
        if barrier
        else str(last.get("move", "HOLD:-"))
    )
    return {
        "step": int(state.step_number),
        "role": "COP",
        "state": [int(state.position[0]), int(state.position[1])],
        "move": move,
        "intent": "truth",
        "hint": str(hint),
    }


def sealed_police_step(state, hint: str) -> dict[str, Any]:
    payload = police_step_payload(state, hint)
    return {"payload": payload, **seal(payload)}


def audit_records(
    records: list[dict[str, Any]], received: dict[int, str] | None = None
) -> dict[str, Any]:
    """Verify a reference-v3 chain, optionally against live commitments."""
    failed: list[int] = []
    forged: list[int] = []
    unsolicited: list[int] = []
    seen: set[int] = set()
    verified = 0
    last_received = max(received) if received else 0

    for index, record in enumerate(records):
        payload = record.get("payload") if isinstance(record, dict) else None
        step = _step_of(payload, index)
        nonce = record.get("nonce") if isinstance(record, dict) else None
        announced = record.get("commit") if isinstance(record, dict) else None
        if (
            not isinstance(payload, dict)
            or not isinstance(nonce, str)
            or not isinstance(announced, str)
        ):
            failed.append(step)
            continue
        seen.add(step)
        if received is not None and step in received and announced != received[step]:
            forged.append(step)
            failed.append(step)
            continue
        if received and step not in received and step < last_received:
            unsolicited.append(step)
            failed.append(step)
            continue
        try:
            verify(payload, nonce, announced)
        except CryptoError:
            failed.append(step)
        else:
            verified += 1

    withheld = sorted(set(received or {}) - seen)
    failed.extend(step for step in withheld if step not in failed)
    return {
        "passed": not failed,
        "verified_steps": verified,
        "failed_steps": sorted(set(failed)),
        "forged_steps": sorted(set(forged)),
        "withheld_steps": withheld,
        "unsolicited_steps": sorted(set(unsolicited)),
    }


def _step_of(payload: dict[str, Any] | None, fallback: int) -> int:
    if isinstance(payload, dict):
        try:
            return int(payload.get("step", fallback))
        except (TypeError, ValueError):
            pass
    return fallback
