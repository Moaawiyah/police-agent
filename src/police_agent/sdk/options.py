"""MatchOptions: everything a caller may choose about one match.

A frozen value object rather than a handful of keyword arguments, because these
four settings are exactly what a front end collects from its user -- argparse
flags today, a GUI form at step 8 -- and passing them as one object means adding
a fifth does not change the signature of every layer in between.

`port` and `opponent_url` default to None rather than to a number: they have no
value worth guessing, so None means "whatever the private `game.toml` says" and
the SDK resolves it. An override that silently shadowed the config would make a
peer play on a port its own config file does not name.
"""

from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_DIR = "config/police"
DEFAULT_HOST = "127.0.0.1"


@dataclass(frozen=True)
class MatchOptions:
    """The caller's choices for one sub-game."""

    config_dir: str | Path = DEFAULT_CONFIG_DIR
    host: str = DEFAULT_HOST
    port: int | None = None
    opponent_url: str | None = None
