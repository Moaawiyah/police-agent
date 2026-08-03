"""Reading a saved match log back: normalisation, re-verification, labels.

Pure functions over plain dicts, with no Tk anywhere, because this is the half
of the replay player that can actually be tested -- and the half that has to be
right. A player that drew the wrong board would be obvious; one that reported
`verified OK` over a tampered record would not.

Two log shapes are accepted. Ours writes the summary at the top level; the
course reference nests it under `"summary"`. Reading both is not politeness: the
league (ch. 9.4) has us replay another group's log, and a player that could only
open its own would be evidence of nothing.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.exceptions import CryptoError

VERIFIED = "verified OK"
TAMPERED = "TAMPERED"
UNKNOWN = "-"


def normalize_log(log_data: dict) -> dict:
    """One uniform view of a match log, whichever of the two shapes it arrived in.

    Every field has a fallback. A log missing its smell `history` replays with a
    flat belief map rather than refusing to open: the commit re-verification is
    the part that carries weight, and it does not need the scent to run.
    """
    body = log_data.get("summary") if isinstance(log_data.get("summary"), dict) else log_data
    return {
        "records": body.get("records") or log_data.get("records") or [],
        "history": body.get("history", []),
        "my_log": body.get("my_log", []),
        "role": body.get("role", "police"),
        "result": body.get("result", UNKNOWN),
        "winner": body.get("winner") or "nobody",
        "group": body.get("group_name") or body.get("group_id", "unnamed"),
        "duration_seconds": body.get("duration_seconds", 0),
        "audit": body.get("audit") or {"passed": True, "verified_steps": 0},
        "reliability": body.get("opponent_reliability"),
    }


def verify_record(records: list, index: int) -> str:
    """Re-run the SHA-256 over one revealed record, exactly as the audit does.

    Recomputed here rather than read from the stored audit result, because a log
    can be edited after it was written. Trusting `audit.passed` from inside the
    same file would let a forged log certify itself.
    """
    if index >= len(records):
        return UNKNOWN
    record = records[index]
    try:
        CommitReveal.verify(record["payload"], record["nonce"], record["commit"])
    except (CryptoError, KeyError, TypeError):
        return TAMPERED
    return VERIFIED


def move_labels(record: dict, verdict: str) -> dict:
    """The panel labels for one replayed step, read out of its sealed payload."""
    payload = record.get("payload") or {}
    commit = str(record.get("commit", UNKNOWN))
    return {
        "verdict": f"{payload.get('rationale', UNKNOWN)} (revealed)",
        "commit": f"{commit[:32]}... [{verdict}]",
    }


def opponent_positions(opponent_log: dict | None) -> list:
    """Per-step true positions from the opponent's own revealed log, if we have it.

    During play this is unknowable by design. After both peers have revealed,
    it is simply history -- which is the only reason the replay may draw two
    agents where the live window can only ever draw one.
    """
    if not opponent_log:
        return []
    return [entry["position"] for entry in normalize_log(opponent_log)["my_log"]]


def frozen_message(index: int, my_steps: int, opponent_steps: int) -> str | None:
    """Name any agent whose track has run out, so a frozen marker is not read as a stall.

    The two logs are rarely the same length: whoever ended the game took the
    last turn. Playback runs to the longer track and holds the shorter agent
    still, which needs saying on the board or it looks like a bug.
    """
    frozen = []
    if index >= my_steps:
        frozen.append("police")
    if opponent_steps and index >= opponent_steps:
        frozen.append("thief")
    return " | ".join(f"{role} track ended (frozen)" for role in frozen) or None
