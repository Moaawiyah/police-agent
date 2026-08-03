"""The `police-agent` CLI: one front end over the SDK, holding no game logic.

Its whole job is the terminal -- read flags, print lines, choose an exit code.
Everything between those two is `PoliceAgentSDK`, which is what lets the window
be a second front end rather than a second implementation.

Three ways to run, all over the same SDK object: headless (the default, and what
a league match uses), `--gui` for the live board, and `--replay` to open a saved
match log in the Visual Replay Player instead of playing at all.

Two settings have no defaults worth guessing -- the port this peer listens on
and the URL of the opponent -- so they come from `config/police/game.toml` and
can be overridden per run, which is what makes it practical to start both peers
on one machine during development.
"""

import argparse
import sys

from police_agent.exceptions import PoliceAgentError
from police_agent.sdk import DEFAULT_CONFIG_DIR, DEFAULT_HOST, MatchOptions, PoliceAgentSDK


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="police-agent", description="Play the police side.")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, help="overrides network.my_port")
    parser.add_argument("--opponent", help="overrides network.opponent_url")
    parser.add_argument("--summary", help="write the match summary to this JSON file")
    parser.add_argument("--gui", action="store_true", help="play with the live board window")
    parser.add_argument("--replay", help="replay a saved match log instead of playing")
    parser.add_argument(
        "--opponent-log",
        help="the thief's revealed log, so the replay can draw both agents",
    )
    return parser.parse_args(argv)


def _options(args: argparse.Namespace) -> MatchOptions:
    """Flags as the SDK wants them; the only translation this module performs."""
    return MatchOptions(
        config_dir=args.config_dir,
        host=args.host,
        port=args.port,
        opponent_url=args.opponent,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        agent = PoliceAgentSDK(_options(args))
        if args.replay:
            return _replay(agent, args)
        summary = _play_with_window(agent) if args.gui else _play_headless(agent)
    except PoliceAgentError as exc:
        # Our own deliberate errors carry a message written to be read. A genuine
        # bug is left to raise with its traceback intact.
        print(f"police-agent: {exc}", file=sys.stderr)
        return 1

    if summary is None:  # the window was closed before the match was started
        print("no match played")
        return 0
    print(f"result={summary['result']} winner={summary['winner']} steps={summary['steps']}")
    if args.summary:
        agent.save_summary(summary, args.summary)
    return 0


def _play_headless(agent: PoliceAgentSDK) -> dict:
    agent.connect()  # bind first, so the line below is true when it is printed
    print(
        f"police listening on {agent.host}:{agent.port}, opponent at {agent.opponent_url}",
        file=sys.stderr,
    )
    return agent.play()


def _play_with_window(agent: PoliceAgentSDK) -> dict | None:
    """Open the live board. Imported here so a headless run never needs Tk."""
    from police_agent.gui.player import LivePeerApp

    return LivePeerApp(agent).run()


def _replay(agent: PoliceAgentSDK, args: argparse.Namespace) -> int:
    from police_agent.gui.replay import ReplayApp

    opponent = agent.load_summary(args.opponent_log) if args.opponent_log else None
    ReplayApp(agent.config, agent.load_summary(args.replay), opponent_log=opponent).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
