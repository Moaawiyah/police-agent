"""Loading local secrets from a gitignored `.env`, once, at startup.

Credentials must not live in `config/police/game.toml`: that file is compared
with the opponent's copy and travels with the repository, so a key written
there is a key published. They belong in the environment -- and a `.env` the
repository ignores is the ordinary way to put them there without retyping an
export in every terminal.

Deliberately small and dependency-free: `KEY=value` lines, `#` comments, blank
lines skipped, optional surrounding quotes stripped. An existing environment
variable always wins, so `ZAI_API_KEY=... uv run ...` overrides the file rather
than being silently ignored by it.
"""

import os
from pathlib import Path

ENV_FILE = ".env"


def load_dotenv(path: str | Path = ENV_FILE) -> dict:
    """Set any variable the file defines that is not already in the environment.

    Returns what it set, names only -- never values, so a caller that logs the
    result cannot leak a key. A missing or unreadable file is not an error: this
    is a convenience, and every one of its callers has to work without it.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    loaded = {}
    for line in text.splitlines():
        name, value = _pair(line)
        if name and name not in os.environ:
            os.environ[name] = value
            loaded[name] = True
    return loaded


def _pair(line: str) -> tuple[str, str]:
    """One `KEY=value` line, or `("", "")` for a comment, blank or malformed one."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return "", ""
    name, _, value = stripped.partition("=")
    return name.strip(), value.strip().strip("'\"")


__all__ = ["ENV_FILE", "load_dotenv"]
