"""Command-line entry point: start this peer's server and play one sub-game.

Two settings have no defaults worth guessing -- the port this peer listens on
and the URL of the opponent -- so they come from `config/police/game.toml` and
can be overridden per run, which is what makes it practical to start both peers
on one machine during development.
"""

import argparse
import json
import sys

from police_agent.constants import Role
from police_agent.exceptions import PoliceAgentError
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import start_peer_server
from police_agent.peer.runtime import PoliceRuntime
from police_agent.shared.config import load_config

DEFAULT_CONFIG_DIR = "config/police"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="police-agent", description="Play the police side.")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, help="overrides network.my_port")
    parser.add_argument("--opponent", help="overrides network.opponent_url")
    parser.add_argument("--summary", help="write the match summary to this JSON file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config = load_config(args.config_dir)
        port = args.port or config.require("network.my_port")
        opponent = args.opponent or config.require("network.opponent_url")

        inboxes = start_peer_server(Role.POLICE, args.host, int(port))
        transport = McpTransport(opponent, inboxes)
        print(f"police listening on {args.host}:{port}, opponent at {opponent}", file=sys.stderr)

        summary = PoliceRuntime(config, transport).run()
    except PoliceAgentError as exc:
        # Our own deliberate errors carry a message written to be read. A genuine
        # bug is left to raise with its traceback intact.
        print(f"police-agent: {exc}", file=sys.stderr)
        return 1

    print(f"result={summary['result']} winner={summary['winner']} steps={summary['steps']}")
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
