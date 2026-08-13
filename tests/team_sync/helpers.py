"""Shared test scaffolding for team_sync: a settled payload builder and a
lightweight Police-shaped summary for filing sub-game 1 directly.
"""

from police_agent.team_sync.import_adapter import compute_result_hash
from police_agent.team_sync.messages import SCHEMA_VERSION, SUBGAME_RESULT

OWN = {"group_id": "OURTEAM", "group_name": "Our Team"}
OPPONENT = {"group_id": "THEIRTEAM", "group_name": "Their Team"}


def settled_payload(
    sub_game_number: int, series_id: str = "series-1", result: str = "capture"
) -> dict:
    """A well-formed `SettledSubgameResult` for one Thief-played sub-game."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "type": SUBGAME_RESULT,
        "series_id": series_id,
        "message_id": f"msg-{sub_game_number}",
        "game_id": "ourteam-vs-theirteam",
        "game_uid": "uid-1",
        "sub_game_number": sub_game_number,
        "sender_role": "thief",
        "status": "settled",
        "result": result,
        "winner": "thief",
        "started_at": "2026-08-01T10:00:00",
        "ended_at": "2026-08-01T10:05:00",
        "duration_seconds": 300.0,
        "steps": 12,
        "identity": OWN,
        "peer_identity": OPPONENT,
        "terms": {"num_games": 2},
        "step_zero": {"sub_game_number": sub_game_number},
        "audit": {"passed": result != "tamper_forfeit", "verified_steps": 12, "failed_steps": []},
        "tokens": {"tokens_total": 0, "peer_tokens_total": 0},
        "records": [],
        "opponent_records": [],
        "history": [],
        "my_log": [],
    }
    payload["result_hash"] = compute_result_hash(payload)
    payload["hmac"] = ""
    return payload


def police_summary(sub_game_number: int) -> dict:
    """A minimal Police-shaped summary, for filing an odd sub-game directly
    (mirrors `peer/summary.py::build_summary()`'s shape, stubbed)."""
    return {
        "result": "survival",
        "winner": None,
        "abort_reason": None,
        "role": "police",
        "steps": 30,
        "unique_cells": 10,
        "barriers_used": 1,
        "started_at": "2026-08-01T09:00:00",
        "ended_at": "2026-08-01T09:05:00",
        "duration_seconds": 300.0,
        "group_name": OWN["group_name"],
        "peer_identity": OPPONENT,
        "terms": {"num_games": 2},
        "identity": OWN,
        "step_zero": {"sub_game_number": sub_game_number},
        "audit": {"passed": True, "verified_steps": 30, "failed_steps": []},
        "opponent_reliability": 0.8,
        "tokens": {"tokens_total": 0, "peer_tokens_total": 0},
        "gatekeeper": {},
        "inbound_dos": {},
        "hint_readings": [],
        "disputes": [],
        "records": [],
        "opponent_records": [],
        "history": [],
        "my_log": [],
        "belief_log": [],
    }
