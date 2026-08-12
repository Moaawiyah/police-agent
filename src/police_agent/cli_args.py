"""Argument parsing for the police-agent command line."""

import argparse

from police_agent.sdk import DEFAULT_CONFIG_DIR, DEFAULT_HOST, DEFAULT_REPORT_DIR, MatchOptions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define and parse every police-agent command-line flag."""
    parser = argparse.ArgumentParser(prog="police-agent", description="Play the police side.")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, help="overrides network.my_port")
    parser.add_argument("--opponent", help="overrides network.opponent_url")
    parser.add_argument("--summary", help="write the match summary to this JSON file")
    parser.add_argument(
        "--report",
        action="store_true",
        help="write the four mandatory report artifacts (ch. 9.3.3)",
    )
    parser.add_argument(
        "--report-dir",
        default=DEFAULT_REPORT_DIR,
        help=f"where --report writes; files land in <dir>/<group_id>/ (default: {DEFAULT_REPORT_DIR})",
    )
    parser.add_argument("--gui", action="store_true", help="play with the live board window")
    parser.add_argument(
        "--series",
        action="store_true",
        help="play the whole agreed series (game.num_games) instead of one sub-game",
    )
    parser.add_argument("--replay", help="replay a saved match log instead of playing")
    parser.add_argument("--opponent-log", help="the thief's revealed log for replay")
    parser.add_argument(
        "--export",
        help="with --replay: render the log to this .gif or .mp4 instead of opening a window "
        "(e.g. results/match.gif)",
    )
    parser.add_argument(
        "--tunnel", action="store_true", help="publish my server on a public ngrok URL"
    )
    parser.add_argument(
        "--league",
        action="store_true",
        help="enforce the public-tunnel league profile (requires --tunnel)",
    )
    return parser.parse_args(argv)


def options_from(args: argparse.Namespace) -> MatchOptions:
    """Translate parsed flags into the SDK's public options object."""
    return MatchOptions(
        config_dir=args.config_dir,
        host=args.host,
        port=args.port,
        opponent_url=args.opponent,
        tunnel=args.tunnel,
        league=args.league,
    )
