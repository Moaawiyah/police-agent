#!/usr/bin/env python3
"""Play one live police-agent match, save its summary, then open the replay.

Outside src/police_agent on purpose (scripts/record_match.sh sets the same
precedent): chaining a live match straight into its own replay is orchestration,
not game logic (CLAUDE.md: domain logic independent of GUI/tooling).

Assumes the opponent (thief) peer is already listening -- this repo never
starts the other side (spec ch. 2.4.2).

Usage:
    uv run scripts/play_and_replay.py
    uv run scripts/play_and_replay.py --opponent http://127.0.0.1:8802/mcp
    uv run scripts/play_and_replay.py --summary logs/my-match.json

Writes:
    logs/police-match-<timestamp>.json   (the match summary, unless --summary)
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from police_agent.cli_actions import play_with_window
from police_agent.gui.replay import ReplayApp
from police_agent.sdk import DEFAULT_CONFIG_DIR, MatchOptions, PoliceAgentSDK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--opponent", help="overrides network.opponent_url")
    parser.add_argument("--port", type=int, help="overrides network.my_port")
    parser.add_argument(
        "--summary",
        help="where to save the match summary (default: logs/police-match-<timestamp>.json)",
    )
    args = parser.parse_args(argv)

    summary_path = Path(args.summary or _default_summary_path())
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    agent = PoliceAgentSDK(
        MatchOptions(config_dir=args.config_dir, opponent_url=args.opponent, port=args.port)
    )
    agent.connect()
    print(
        f"police listening on {agent.host}:{agent.port}, opponent at {agent.opponent_url}",
        file=sys.stderr,
    )
    summary = play_with_window(agent)
    if summary is None:
        print("no match played", file=sys.stderr)
        return 0

    agent.save_summary(summary, summary_path)
    print(f"result={summary['result']} winner={summary['winner']} steps={summary['steps']}")
    print(f"summary: {summary_path}", file=sys.stderr)

    ReplayApp(agent.config, summary).run()
    return 0


def _default_summary_path() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"logs/police-match-{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
