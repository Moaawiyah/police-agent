"""Putting the four artifacts on disk, under the names the schema fixes.

Ch. 9.3.3 derives every filename from the `game_id` so files from different
matches can never be mixed: `declaration_<game_id>.json` and
`result_<game_id>.json` describe the whole series, while
`config_<game_id>_g<NN>.json` and `log_<game_id>_g<NN>.json` describe one
sub-game each. They are written under `<base>/<own_group_id>/`, so a machine that
played both sides of a practice match keeps the two teams' reports apart.

## Why a fifth file is written

The result artifact must cover *every* sub-game, but a sub-game runs in its own
process (ch. 2.4.2) and only ever holds its own. So each run also files the raw
match record it was handed, as `record_<game_id>_g<NN>.json`, and a later run
picks its siblings up from there.

It is the same object `--summary` already writes, filed under a discoverable
name; it is not a fifth *schema* artifact and the `links` block does not mention
it. The alternative would be to reconstruct earlier sub-games from their log
artifacts, which are projections -- and a projection cannot be un-projected
without inventing the parts it dropped, which in this case includes the opponent's
declared commit for a game this process never saw.

Sub-games are read back by number rather than by directory order, and the current
one always replaces its own file, so a replayed sub-game corrects the series
rather than appearing in it twice.

## A rematch against the same opponent is a different problem

`game_id` has no clock in it, so a second series against a group we have
already played would land on the first series' files too -- not a replay to
correct, but a different match to keep. Sub-game 1 checks for that first;
see `report/history.py`.
"""

import json
from pathlib import Path

from police_agent.report.artifacts import build_config, build_log
from police_agent.report.declaration import build_declaration
from police_agent.report.facts import facts_from
from police_agent.report.history import archive_completed_series
from police_agent.report.ids import sub_game_tag
from police_agent.report.result import build_result, scoring_from

RECORD_PREFIX = "record"


def write_artifacts(summary: dict, base: str | Path = "logs", config=None) -> dict:
    """Write all four artifacts for this sub-game, and return where each landed.

    The result covers the whole series: this sub-game's record plus every sibling
    already filed under the same `game_id`. Sub-game 1 first archives a finished
    prior series against this opponent, if one is sitting in the way.
    """
    facts = facts_from(summary, config)
    directory = report_dir(base, facts.own_group_id)
    if facts.sub_game_number == 1:
        archive_completed_series(directory, facts)
    paths = artifact_paths(directory, facts)

    _write(paths["record"], summary)
    _write(paths["declaration"], build_declaration(facts, summary))
    _write(paths["config"], build_config(facts, summary, config))
    _write(paths["log"], build_log(facts, summary))
    series = series_records(directory, facts.game_id)
    _write(paths["result"], build_result(facts, series, scoring_from(config)))
    return paths


def report_dir(base: str | Path, group_id: str) -> Path:
    """`<base>/<own_group_id>/`, created if it is not there yet."""
    directory = Path(base) / group_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def artifact_paths(directory: Path, facts) -> dict:
    """Every filename this sub-game writes, derived from the two identifiers."""
    tag = sub_game_tag(facts.sub_game_number)
    return {
        "declaration": directory / f"declaration_{facts.game_id}.json",
        "config": directory / f"config_{facts.game_id}_{tag}.json",
        "log": directory / f"log_{facts.game_id}_{tag}.json",
        "result": directory / f"result_{facts.game_id}.json",
        "record": directory / f"{RECORD_PREFIX}_{facts.game_id}_{tag}.json",
    }


def series_records(directory: Path, game_id: str) -> list:
    """Every sub-game of *this* match filed in this directory, in sub-game order.

    Keyed on the `game_id` rather than on the directory, because one group plays
    several opponents and a record from another match would be folded into the
    wrong series -- the exact mixing ch. 9.3.3 derives the filenames to prevent.

    A file that will not parse is skipped rather than raised on. A half-written
    record from an interrupted run must not stop the report of the sub-games that
    did finish -- rule 35 costs both teams the match for a report that never
    arrived, and nothing at all for one that is short a game.
    """
    found = []
    for path in sorted(directory.glob(f"{RECORD_PREFIX}_{game_id}_*.json")):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(found, key=_sub_game_number)


def _sub_game_number(summary: dict) -> int:
    return int((summary.get("step_zero") or {}).get("sub_game_number", 1))


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
