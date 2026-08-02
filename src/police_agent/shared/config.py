"""Configuration: the agreed terms, plus this peer's own private settings.

Two files, deliberately in two formats and two roles (README, "Configuration"):

* `game.json` -- the terms both peers signed. Byte-identical on both sides.
* `game.toml` -- this peer's private settings: its port, the opponent's URL, an
  optional strategy selector. Never shared, never committed.

The agreed file is overlaid *on top of* the private one, so a shared term always
wins. That ordering is the point: if the private file could override
`board.size` or `rules.barriers_max`, a peer could sign one set of terms and
quietly play another, and the pre-game signature check would not catch it
because it verifies the agreed file, not what the code ended up using.
"""

import json
import tomllib
from pathlib import Path
from typing import Any

from police_agent.exceptions import ConfigError
from police_agent.shared.schema import deep_merge, dig, translate_shared

GAME_JSON = "game.json"
GAME_TOML = "game.toml"


class Config:
    """Merged configuration, read by dotted key."""

    def __init__(self, data: dict, shared: dict | None = None) -> None:
        self._data = data
        self._shared = shared or {}

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """The value at `dotted_key`, e.g. `board.size`, or `default`."""
        return dig(self._data, dotted_key, default)

    def require(self, dotted_key: str) -> Any:
        """The value at `dotted_key`, or a ConfigError naming what is missing.

        For settings with no sensible default, where continuing on a `None`
        would fail much later and much less legibly.
        """
        value = self.get(dotted_key)
        if value is None:
            raise ConfigError(f"Missing required config key {dotted_key!r}")
        return value

    @property
    def shared(self) -> dict:
        """The agreed `game.json` exactly as read, for signing and comparison."""
        return self._shared


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def _load_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc


def load_config(config_dir: str | Path) -> Config:
    """Load `game.json` and, when present, this peer's private `game.toml`.

    The private file is optional so the agent can be driven entirely from
    arguments in a test or a scripted run; the agreed file is not, because
    without it there are no terms to play by.
    """
    directory = Path(config_dir)
    if not directory.is_dir():
        raise ConfigError(f"Config directory not found: {directory}")

    shared = _load_json(directory / GAME_JSON)
    private_path = directory / GAME_TOML
    data = _load_toml(private_path) if private_path.is_file() else {}
    deep_merge(data, translate_shared(shared))
    return Config(data, shared)
