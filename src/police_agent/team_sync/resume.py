"""Recover a resumed team_sync series' already-settled sub-games from disk.

Split out of scheduler.py to keep it under the project's per-file line cap.
"""

import json

from police_agent.report.facts import facts_from
from police_agent.report.writer import RECORD_PREFIX, report_dir, series_records

__all__ = ["backfill_missing_summaries"]


def backfill_missing_summaries(agent, base: str, group_id: str, summaries: list[dict]) -> None:
    """Fill any `{}` placeholder left by a resume that skips an
    already-settled sub-game (`scheduler.py::_resume_or_start`) from the
    record artifacts every sub-game already wrote to disk.

    Without this, a series resumed mid-flight understates its own final
    score (`_notify_game_over`'s totals sum whatever is in `summaries`
    verbatim), and a subsequent `--report` files spurious `unknown-group`
    artifacts for the leftover empty placeholders.
    """
    if all(summaries):
        return
    directory = report_dir(base, group_id)
    existing = sorted(directory.glob(f"{RECORD_PREFIX}_*.json"))
    if not existing:
        return
    seed = json.loads(existing[0].read_text(encoding="utf-8"))
    game_id = facts_from(seed, agent.config).game_id
    by_number = {
        int((record.get("step_zero") or {}).get("sub_game_number", 0)): record
        for record in series_records(directory, game_id)
    }
    for index, summary in enumerate(summaries):
        if not summary and (index + 1) in by_number:
            summaries[index] = by_number[index + 1]
