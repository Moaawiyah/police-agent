"""Atomic on-disk persistence for team_sync: the local state machine survives
a restart, a retried `subgame_result` is deduplicated, and the final email is
sent at most once per game -- across process restarts, not just in memory.

Every write goes to `<name>.tmp` then `os.replace`, so a crash mid-write
leaves the previous, still-valid file in place rather than a half-written
one `json.loads` would choke on.
"""

import json
import os
from pathlib import Path

from police_agent.team_sync.state import SeriesSyncStatus

STATE_FILE = "team_sync_state.json"
SEEN_FILE = "team_sync_seen.json"
EMAIL_FILE = "team_sync_email.json"


def _atomic_write_json(path: Path, data) -> None:
    """Write `data` to `path` as JSON, never leaving a half-written file behind."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default):
    """`default` for a missing or unparsable file, never an exception."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class TeamSyncStore:
    """One series' team_sync bookkeeping, filed under `<directory>/`."""

    def __init__(self, directory: str | Path) -> None:
        """Where this peer's team_sync files live -- created if not there yet."""
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def load_status(self) -> SeriesSyncStatus | None:
        """The persisted `SeriesSyncStatus`, or `None` if no series has started."""
        data = _read_json(self._directory / STATE_FILE, None)
        return SeriesSyncStatus.from_dict(data) if data else None

    def save_status(self, status: SeriesSyncStatus) -> None:
        """Persist `status`, replacing whatever was filed before it."""
        _atomic_write_json(self._directory / STATE_FILE, status.to_dict())

    def reset(self) -> None:
        """Drop the persisted state: a fresh series against a possibly new opponent."""
        path = self._directory / STATE_FILE
        if path.exists():
            path.unlink()

    def seen(self, key: str) -> bool:
        """Whether `key` (an idempotency key) has already been recorded."""
        return key in _read_json(self._directory / SEEN_FILE, [])

    def mark_seen(self, key: str) -> None:
        """Record `key` as handled, so a retried message is not applied twice."""
        keys = _read_json(self._directory / SEEN_FILE, [])
        if key not in keys:
            keys.append(key)
            _atomic_write_json(self._directory / SEEN_FILE, keys)

    def email_sent(self, game_id: str, report_hash: str) -> bool:
        """Whether the final report for `game_id` at `report_hash` was already mailed."""
        marker = _read_json(self._directory / EMAIL_FILE, {})
        entry = marker.get(game_id) or {}
        return bool(entry.get("email_sent") and entry.get("final_report_hash") == report_hash)

    def mark_email_sent(self, game_id: str, report_hash: str) -> None:
        """Record that `game_id`'s report at `report_hash` was mailed, once."""
        marker = _read_json(self._directory / EMAIL_FILE, {})
        marker[game_id] = {"final_report_hash": report_hash, "email_sent": True}
        _atomic_write_json(self._directory / EMAIL_FILE, marker)


__all__ = ["TeamSyncStore"]
