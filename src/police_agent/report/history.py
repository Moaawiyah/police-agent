"""Keeping a rematch against the same opponent from overwriting the last one.

`report/ids.py`'s `game_id` is the sorted pair of group ids and nothing else
-- no clock, no run number -- because both peers must derive the same match
name without talking. That is correct for naming *one* match, but it means
every series ever played against a given opponent wants the same filenames:
`declaration_<game_id>.json`, `result_<game_id>.json`, and each sub-game's
`config_/log_/record_<game_id>_g<NN>.json`. Play the same group twice and a
rematch's sub-game 1 lands on the first series' files -- and if the rematch
has not yet reached as many sub-games as the old one had, `writer.py`'s own
`series_records()` glob would fold the old series' leftover sub-games into
the new one's result.

So before a sub-game 1 is written, this module checks whether the files
already sitting there belong to a *finished* series and, if so, moves them
aside first. "Finished" is read off the result artifact itself:
`report/result.py` already writes `num_sub_games` (how many are on file) and
`num_sub_games_agreed` (the signed target) into every result, and
`peer/series.py::run_series` never stops short of that target -- a technical
loss is still that sub-game's result, and the only early exit unwinds the
*whole* series back to sub-game 1 rather than leaving a partial one on disk.
So a result below its own target is an in-progress (or crash-restarted)
series, not a finished one, and is left alone -- the same "corrects in place"
behaviour `writer.py` already relies on for a replayed sub-game 1.

The archive and the ledger it writes to (`series_history.json`) are local
bookkeeping only, never crossing the wire. Same philosophy as
`shared/quota.py`: a corrupt or missing file degrades to "nothing on
record" rather than raising -- a damaged local file is a worse count, not a
reason to block a report.
"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["archive_completed_series", "count_series"]

RESULT_PREFIX = "result"
DECLARATION_PREFIX = "declaration"
CONFIG_PREFIX = "config"
LOG_PREFIX = "log"
RECORD_PREFIX = "record"
HISTORY_FILE = "series_history.json"
ARCHIVE_DIR = "archive"


def archive_completed_series(directory: Path, facts, now=lambda: datetime.now(UTC)) -> bool:
    """Move a finished prior series against this opponent out of the way.

    A no-op unless `directory` already holds a `result_<game_id>.json` whose
    own `num_sub_games` reached its own `num_sub_games_agreed` -- see the
    module docstring for why that is a safe test. Returns whether anything
    moved. A destination that cannot be created is a worse archive, not a
    reason to fail the report the caller is about to write, so it is caught
    here rather than left to surface from `write_artifacts`.
    """
    old = _read_json(directory / f"{RESULT_PREFIX}_{facts.game_id}.json")
    if not _is_complete(old):
        return False
    moment = now()
    destination = directory / ARCHIVE_DIR / f"{moment:%Y%m%dT%H%M%SZ}_{facts.game_id}"
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    for path in _series_files(directory, facts.game_id):
        _move(path, destination / path.name)
    _append_history(directory, facts, old, moment)
    return True


def count_series(directory: Path, opponent_group_id: str | None = None) -> int:
    """How many completed series are on record, optionally against one opponent.

    The driftproof answer to "how many series against group X" -- read off the
    ledger `archive_completed_series` maintains, not kept in anyone's head.
    """
    entries = _read_json(directory / HISTORY_FILE)
    entries = entries if isinstance(entries, list) else []
    if opponent_group_id is None:
        return len(entries)
    return sum(1 for entry in entries if entry.get("opponent_group_id") == opponent_group_id)


def _is_complete(old) -> bool:
    if not isinstance(old, dict):
        return False
    agreed, played = old.get("num_sub_games_agreed"), old.get("num_sub_games")
    both_ints = all(
        isinstance(value, int) and not isinstance(value, bool) for value in (agreed, played)
    )
    return both_ints and played >= agreed


def _series_files(directory: Path, game_id: str) -> list[Path]:
    """Every file this series wrote; matched like `series_records`, never a substring."""
    exact = [
        directory / f"{prefix}_{game_id}.json" for prefix in (DECLARATION_PREFIX, RESULT_PREFIX)
    ]
    found = [path for path in exact if path.is_file()]
    for prefix in (CONFIG_PREFIX, LOG_PREFIX, RECORD_PREFIX):
        found.extend(sorted(directory.glob(f"{prefix}_{game_id}_*.json")))
    return found


def _append_history(directory: Path, facts, old: dict, moment: datetime) -> None:
    """Log the archived series. Timing/outcome come from `old`, the series being
    filed away, never from `facts`, which describes the new call overwriting it."""
    entries = _read_json(directory / HISTORY_FILE)
    entries = entries if isinstance(entries, list) else []
    entries.append(
        {
            "game_id": facts.game_id,
            "game_uid": old.get("game_uid", facts.game_uid),
            "opponent_group_id": facts.opponent_group_id,
            "own_group_id": facts.own_group_id,
            "num_sub_games": old.get("num_sub_games"),
            "final_result": old.get("final_result"),
            "started_at": old.get("game_started_at"),
            "ended_at": old.get("game_ended_at"),
            "archived_at": moment.isoformat(),
        }
    )
    _write_json(directory / HISTORY_FILE, entries)


def _move(source: Path, target: Path) -> None:
    try:
        shutil.move(str(source), str(target))
    except OSError:
        return


def _read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return
