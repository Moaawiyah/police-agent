"""The police-agent CLI: parse flags, invoke the SDK, and print the result."""

import sys

from police_agent.cli_actions import (
    announce_tunnel,
)
from police_agent.cli_actions import (
    play_headless as _play_headless,
)
from police_agent.cli_actions import (
    play_series_headless as _play_series_headless,
)
from police_agent.cli_actions import (
    play_with_window as _play_with_window,
)
from police_agent.cli_actions import (
    replay as _replay,
)
from police_agent.cli_actions import (
    report as _report,
)
from police_agent.cli_actions import (
    report_series as _report_series,
)
from police_agent.cli_args import options_from as _options
from police_agent.cli_args import parse_args as _parse_args
from police_agent.exceptions import PoliceAgentError
from police_agent.sdk import PoliceAgentSDK

_announce_tunnel = announce_tunnel


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        agent = PoliceAgentSDK(_options(args))
        if args.replay:
            return _replay(agent, args)
        if args.gui:
            return _play_gui(agent, args)
        if args.series:
            return _play_series(agent, args)
        summary = _play_headless(agent)
    except PoliceAgentError as exc:
        print(f"police-agent: {exc}", file=sys.stderr)
        return 1

    if summary is None:
        print("no match played")
        return 0
    print(f"result={summary['result']} winner={summary['winner']} steps={summary['steps']}")
    if args.summary:
        agent.save_summary(summary, args.summary)
    if args.report:
        _report(agent, summary, args.report_dir)
    return 0


def _play_gui(agent, args) -> int:
    """The GUI's Start button always plays the whole series (`gui/player.py`),
    never one sub-game -- so, like `_play_series` below, it reports through
    `_finish_series`: one writer for both, rather than two that can quietly
    disagree about how many sub-games actually got saved."""
    return _finish_series(agent, args, _play_with_window(agent))


def _play_series(agent, args) -> int:
    return _finish_series(agent, args, _play_series_headless(agent))


def _finish_series(agent, args, summaries: list[dict]) -> int:
    if not summaries:
        print("no match played")
        return 0
    for summary in summaries:
        print(f"result={summary['result']} winner={summary['winner']} steps={summary['steps']}")
    if args.summary:
        agent.save_summary(summaries[-1], args.summary)
    if args.report:
        _report_series(agent, summaries, args.report_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
