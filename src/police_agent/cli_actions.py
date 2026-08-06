"""Terminal actions shared by the small command-line entry point."""

import sys


def report(agent, summary: dict, base: str) -> None:
    paths = agent.write_artifacts(summary, base)
    for role, path in sorted(paths.items()):
        print(f"{role}: {path}", file=sys.stderr)
    mailed = agent.email_report(paths)
    print(mailed or "email reporting is off (set email.enabled in game.toml)", file=sys.stderr)


def play_headless(agent) -> dict:
    agent.connect()
    print(
        f"police listening on {agent.host}:{agent.port}, opponent at {agent.opponent_url}",
        file=sys.stderr,
    )
    announce_tunnel(agent)
    return agent.play()


def announce_tunnel(agent) -> None:
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


def play_with_window(agent):
    """Open Tk lazily so a headless run does not need a display."""
    from police_agent.gui.player import LivePeerApp

    return LivePeerApp(agent).run()


def replay(agent, args) -> int:
    opponent = agent.load_summary(args.opponent_log) if args.opponent_log else None
    log_data = agent.load_summary(args.replay)
    if args.export:
        return _export_replay(agent, log_data, opponent, args.export)
    from police_agent.gui.replay import ReplayApp

    ReplayApp(agent.config, log_data, opponent_log=opponent).run()
    return 0


def _export_replay(agent, log_data: dict, opponent: dict | None, out_path: str) -> int:
    """No Tk anywhere on this path -- runs headless, over SSH or in CI."""
    from police_agent.gui.export import export_replay

    written = export_replay(agent.config, log_data, opponent, out_path)
    print(f"exported: {written}", file=sys.stderr)
    return 0
