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

That local default is why `--tunnel` is a flag rather than the norm: a league
match needs the public URL it prints (Appendix He rule 10), and a practice match
on this machine needs no internet at all.
"""

import argparse
import sys

from police_agent.exceptions import PoliceAgentError
from police_agent.sdk import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_HOST,
    DEFAULT_REPORT_DIR,
    MatchOptions,
    PoliceAgentSDK,
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
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
    parser.add_argument("--replay", help="replay a saved match log instead of playing")
    parser.add_argument(
        "--opponent-log",
        help="the thief's revealed log, so the replay can draw both agents",
    )
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="publish my server on a public ngrok URL (run `ngrok config add-authtoken` first)",
    )
    return parser.parse_args(argv)


def _options(args: argparse.Namespace) -> MatchOptions:
    """Flags as the SDK wants them; the only translation this module performs."""
    return MatchOptions(
        config_dir=args.config_dir,
        host=args.host,
        port=args.port,
        opponent_url=args.opponent,
        tunnel=args.tunnel,
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
    if args.report:
        _report(agent, summary, args.report_dir)
    return 0


def _report(agent: PoliceAgentSDK, summary: dict, base: str) -> None:
    """Write the four artifacts and say where they went.

    Printed rather than silent because the result file is the one a human then
    has to see arrive at the lecturer (rule 32), and a report nobody can find is
    the same as a report nobody sent.

    Mailing is attempted straight afterwards and is inert unless `[email]` in
    `game.toml` switches it on -- the shipped settings write a local draft at
    most, so a practice match never mails anybody.
    """
    paths = agent.write_artifacts(summary, base)
    for role, path in sorted(paths.items()):
        print(f"{role}: {path}", file=sys.stderr)
    mailed = agent.email_report(paths)
    print(mailed or "email reporting is off (set email.enabled in game.toml)", file=sys.stderr)


def _play_headless(agent: PoliceAgentSDK) -> dict:
    agent.connect()  # bind first, so the lines below are true when they are printed
    print(
        f"police listening on {agent.host}:{agent.port}, opponent at {agent.opponent_url}",
        file=sys.stderr,
    )
    _announce_tunnel(agent)
    return agent.play()


def _announce_tunnel(agent: PoliceAgentSDK) -> None:
    """Print the public address, because a human has to send it to the other team.

    An ephemeral URL is called out rather than merely printed: it is a different
    address after every restart, and the opposing team has the old one written
    into their own config, so a silent change reads to them as a peer that has
    gone missing.
    """
    if agent.public_url is None:
        return
    print(f"public URL (give this to the opposing team): {agent.public_url}", file=sys.stderr)
    if agent.tunnel_domain is None:
        print(
            "  this URL is EPHEMERAL and changes every restart. Reserve a domain at "
            "https://dashboard.ngrok.com/domains and set network.tunnel_domain in "
            "config/police/game.toml to keep one address.",
            file=sys.stderr,
        )


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
