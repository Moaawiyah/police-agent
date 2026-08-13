"""The `[team_sync]` private-settings block: this peer's own coordination
address and role, never an agreed (signed) term.

Mirrors `infra/gmail.py::settings()`'s exact idiom: a `DEFAULTS` dict merged
with whatever `config.get("team_sync.<key>")` overrides. The shared HMAC
secret is deliberately absent from both the defaults and the schema here --
it comes only from the `TEAM_SYNC_SECRET` environment variable
(`security.py`) and must never be written to any config file.
"""

DEFAULT_PORT = 8811

DEFAULTS = {
    "enabled": False,
    "host": "127.0.0.1",
    "port": DEFAULT_PORT,
    "sibling_url": "http://127.0.0.1:8812/mcp",
    "role": "police",
    "series_owner": True,
    "report_owner": True,
}


def settings(config=None) -> dict:
    """The `[team_sync]` block, over the shipped defaults."""
    read = config.get if config is not None else (lambda _key, default=None: default)
    return {key: _or_default(read(f"team_sync.{key}"), value) for key, value in DEFAULTS.items()}


def _or_default(value, default):
    return default if value is None else value
