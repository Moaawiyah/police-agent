"""PoliceAgentSDK: one object holding every capability of the police agent.

Load the agreed terms, open this peer's mailbox, play a sub-game, save the match
record. A front end needs nothing else, and deliberately gets nothing else.

Construction is lazy and idempotent. Reading `agent.port` must not bind a
socket, because a GUI wants to show the settings before the user presses Start;
but `connect()` twice must not open two servers either, since the second would
fail on the port the first is holding. Both fall out of building each piece on
first use and remembering it.

The transport and the config can be injected. That is the same seam the runtime
already exposes for its brain: it is what lets a whole match be played against
`tests/peer/fake_transport.py` with no sockets, no threads and no opponent
process -- and, at step 8, what lets the replay viewer drive the agent from a
recorded log instead of a live wire.
"""

import json
from pathlib import Path

from police_agent.constants import Role
from police_agent.exceptions import ConfigError
from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import start_peer_server
from police_agent.peer.runtime import PoliceRuntime
from police_agent.sdk.options import MatchOptions
from police_agent.shared.config import load_config

# Fallbacks for the two transport deadlines, used only when the agreed
# `game.json` names neither. Both are in the shipped file (Appendix Vav), so
# these numbers should never actually decide a match.
DEFAULT_CONNECT_TIMEOUT = 60.0
DEFAULT_REPLY_TIMEOUT = 30.0


class PoliceAgentSDK:
    """The police agent's public API: configure it, connect it, play a sub-game."""

    def __init__(
        self, options=None, *, config=None, transport=None, listener=None, controls=None
    ) -> None:
        self.options = options or MatchOptions()
        self.config = config if config is not None else load_config(self.options.config_dir)
        self._transport = transport
        self._runtime: PoliceRuntime | None = None
        # Public and reassignable, because the GUI cannot supply them at
        # construction: it needs an SDK to build its window from before it has a
        # window to listen with. Both are read once, when the runtime is built on
        # the first `play()`; setting either after that has no effect.
        self.listener = listener
        self.controls = controls

    @property
    def host(self) -> str:
        """The interface this peer's own server listens on."""
        return self.options.host

    @property
    def port(self) -> int:
        """This peer's port: the caller's override, else `network.my_port`.

        `require` rather than `get`, so a config with no port is reported by name
        before a socket is opened rather than as a `None` deep inside uvicorn.
        """
        return int(self.options.port or self.config.require("network.my_port"))

    @property
    def opponent_url(self) -> str:
        """The one thing this peer knows about its opponent."""
        return str(self.options.opponent_url or self.config.require("network.opponent_url"))

    def connect(self):
        """Open this peer's mailbox and the outbound link, and return the transport.

        Safe to call more than once, and skipped entirely when a transport was
        injected -- so a test double is never quietly replaced by a real socket.
        """
        if self._transport is None:
            inboxes = start_peer_server(Role.POLICE, self.host, self.port)
            self._transport = McpTransport(self.opponent_url, inboxes, **self.transport_timeouts())
        return self._transport

    def transport_timeouts(self) -> dict:
        """The wire deadlines, taken from the agreed terms rather than the code.

        Both peers read them from the byte-identical `game.json`, so agreeing on
        how long to wait is part of agreeing on the game -- a peer that walks
        away early scores a technical win it did not play for.
        """
        return {
            "connect_timeout": float(
                self.config.get("network.watchdog_timeout_seconds") or DEFAULT_CONNECT_TIMEOUT
            ),
            "reply_timeout": float(
                self.config.get("network.response_timeout_seconds") or DEFAULT_REPLY_TIMEOUT
            ),
        }

    @property
    def runtime(self) -> PoliceRuntime:
        """The runtime playing this match, built on first use and kept.

        Kept rather than rebuilt because it *is* the match: its state, its
        sealed log and its belief map are what a caller asking twice expects to
        still be looking at.
        """
        if self._runtime is None:
            self._runtime = PoliceRuntime(
                self.config, self.connect(), listener=self.listener, controls=self.controls
            )
        return self._runtime

    def play(self) -> dict:
        """Play one sub-game against the opponent and return the match summary."""
        return self.runtime.run()

    def load_summary(self, path: str | Path) -> dict:
        """Read back a match record written by `save_summary`, for the replay player.

        A file, not a live game, so it needs no transport and no port -- which is
        what lets a saved match be replayed on a machine that could not play one.
        """
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"Match log not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Match log is not valid JSON: {path}: {exc}") from exc

    def save_summary(self, summary: dict, path: str | Path) -> Path:
        """Write the match record to `path`, so the report and replay can read it.

        The whole record is written, not the headline result: the specification's
        report and the replay viewer are both rebuilt from this file, and a
        summary trimmed to what today's CLI prints would not support either.
        """
        destination = Path(path)
        destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return destination
