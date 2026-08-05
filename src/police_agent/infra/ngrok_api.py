"""Reads the local ngrok agent API and its startup log."""

import json
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "http://127.0.0.1:4040/api/tunnels"


def published_url(port: int, tunnels_getter=None) -> str | None:
    get_tunnels = tunnels_getter or _agent_tunnels
    urls = [
        str(tunnel["public_url"])
        for tunnel in get_tunnels()
        if tunnel.get("public_url") and _forwards_to(tunnel, port)
    ]
    return next((url for url in urls if url.startswith("https://")), urls[0] if urls else None)


def _forwards_to(tunnel: dict, port: int) -> bool:
    return str(tunnel.get("config", {}).get("addr", "")).endswith(f":{port}")


def _agent_tunnels() -> list[dict]:
    try:
        with urllib.request.urlopen(API_URL, timeout=2.0) as response:  # noqa: S310 - local API
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return []
    return [tunnel for tunnel in body.get("tunnels") or [] if isinstance(tunnel, dict)]


def _tail(log: Path, lines: int = 8) -> str:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""
