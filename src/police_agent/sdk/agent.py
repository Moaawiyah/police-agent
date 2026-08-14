"""Lazy, injectable SDK facade for configuring and playing a police match."""

from pathlib import Path

from police_agent.peer.controls import GameControls
from police_agent.peer.runtime import PoliceRuntime
from police_agent.sdk.agent_connection import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_REPLY_TIMEOUT,
    _ConnectionMixin,
)
from police_agent.sdk.options import MatchOptions
from police_agent.sdk.reporting import (
    email_report,
    load_summary,
    save_summary,
    write_artifacts,
)
from police_agent.sdk.series import play_series
from police_agent.shared.config import load_config

__all__ = [
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_REPLY_TIMEOUT",
    "DEFAULT_REPORT_DIR",
    "GameControls",
    "PoliceAgentSDK",
]

DEFAULT_REPORT_DIR = "logs"


class PoliceAgentSDK(_ConnectionMixin):
    """The police agent's public API: configure it, connect it, play a sub-game.

    Connection/runtime-building lives in `_ConnectionMixin`
    (`agent_connection.py`), split out to keep this file under the project's
    line budget; callers see one class either way.
    """

    def __init__(
        self, options=None, *, config=None, transport=None, listener=None, controls=None
    ) -> None:
        """Hold this match's options and config; nothing connects until `connect()`."""
        self.options = options or MatchOptions()
        self.config = config if config is not None else load_config(self.options.config_dir)
        self._transport = transport
        self._runtime: PoliceRuntime | None = None
        self._tunnel = None
        self.listener = listener
        self.controls = controls

    def play(self) -> dict:
        """Play one sub-game to a result."""
        return self.runtime.run()

    def play_series(self) -> list[dict]:
        """Play the whole agreed series."""
        return play_series(self)

    def restart(self) -> None:
        """Drop the finished runtime so the next `play()` builds a fresh one.

        The transport (and the server bound to this port) is left untouched
        and reused -- rebinding it would race the port the old one still
        holds. Only the game state is new: a fresh `PoliceRuntime` negotiates
        its own handshake in `run()`, so this never re-arms a runtime that has
        already agreed its terms (`gui/live_controls.py`'s Start button is
        deliberately not re-armable for that exact reason).
        """
        self._runtime = None

    def load_summary(self, path: str | Path) -> dict:
        """Read a saved match summary from `path`."""
        return load_summary(path)

    def save_summary(self, summary: dict, path: str | Path) -> Path:
        """Write `summary` to `path` as JSON."""
        return save_summary(summary, path)

    def write_artifacts(self, summary: dict, base: str | Path = DEFAULT_REPORT_DIR) -> dict:
        """Write this match's mandatory report artifacts under `base`."""
        return write_artifacts(summary, base, self.config)

    def email_report(self, paths: dict) -> str | None:
        """Mail (or draft) the report at `paths`, per this peer's `[email]`
        config and the `--count` flag (`self.options.counted`)."""
        return email_report(paths, self.config, counted=self.options.counted)
