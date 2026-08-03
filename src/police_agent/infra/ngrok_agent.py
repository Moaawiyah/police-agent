"""Starting ngrok and reading its own local API back.

Split out of `tunnel.py` to keep both files under the project's 150-line rule:
this half is the process -- spawn it, poll its agent API, explain why it died;
`tunnel.py` is the object a caller actually holds and calls `close()` on.

The public URL is read from ngrok's agent API (a fixed local port) rather than
from the process's own output, which is a redrawing terminal UI and not a
format anything should be parsing.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from police_agent.exceptions import ConfigError, PoliceAgentError, TransportError

API_URL = "http://127.0.0.1:4040/api/tunnels"
_POLL_INTERVAL = 0.5

_AUTH_MARKERS = ("err_ngrok_4018", "authtoken")
_TAKEN_MARKERS = ("err_ngrok_334", "err_ngrok_108", "already bound", "simultaneous")


def launch(port: int, domain: str | None, timeout: float):
    """Adopt an existing tunnel for `port`, or start ngrok and wait for one.

    Returns `(public_url, process_or_None, log_or_None)`. The last two are None
    exactly when a tunnel was adopted rather than started: the caller does not
    own that process and must never register it for cleanup.
    """
    adopted = published_url(port)
    if adopted is not None:
        # Something already publishes this port: a peer of ours still running, or
        # a tunnel the user opened by hand. A second ngrok would only fight it for
        # the reserved domain and for the 4040 API, so take it and never kill it.
        return adopted, None, None
    # Resolved before the log exists, so a machine without ngrok is turned away
    # without leaving a temp file behind that nothing will ever read.
    binary = _ngrok_binary()
    # Deleted by the caller's `close`, but deliberately left behind when startup
    # fails: at that point it is the only record of what ngrok objected to.
    log = _new_log()
    process = _spawn(binary, port, domain, log)
    return _wait_for_url(process, port, domain, log, timeout), process, log


def _ngrok_binary() -> str:
    """Where ngrok is, or an error naming both ways out of not having it."""
    binary = shutil.which("ngrok")
    if binary is None:
        raise ConfigError(
            "ngrok is not on PATH. Appendix He rule 10 makes tunnelling mandatory, so\n"
            "either drop --tunnel to play a peer on this machine, or install it:\n"
            "  brew install ngrok   (or see https://ngrok.com/download)\n"
            "  ngrok config add-authtoken <your token>"
        )
    return binary


def _new_log() -> Path:
    """A private file for ngrok's own diagnostics.

    `mkstemp` hands back an open descriptor as well as a path, and ngrok opens
    the file by name itself -- so the descriptor is closed at once rather than
    held for the length of the match doing nothing.
    """
    handle, path = tempfile.mkstemp(prefix="police-ngrok-", suffix=".log")
    os.close(handle)
    return Path(path)


def _spawn(binary: str, port: int, domain: str | None, log: Path) -> subprocess.Popen:
    """Start ngrok, logging to a file of ours so a failure can be explained.

    A pipe is the obvious channel and the wrong one: nobody drains it during a
    match, so a chatty ngrok would fill it, block on its own log, and take the
    tunnel down -- and with it the game.
    """
    command = [binary, "http", str(port), f"--log={log}"]
    if domain:
        command.append(f"--domain={domain}")
    quiet = subprocess.DEVNULL  # ngrok's terminal UI goes nowhere; the log file is the record
    return subprocess.Popen(command, stdin=quiet, stdout=quiet, stderr=quiet)


def _wait_for_url(process, port: int, domain: str | None, log: Path, timeout: float) -> str:
    """Poll the agent API until it publishes our port, or say why it never will."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        url = published_url(port)
        if url is not None:
            return url
        if process.poll() is not None:
            raise _startup_failure(_tail(log), domain)
        time.sleep(_POLL_INTERVAL)
    process.terminate()  # a survivor would keep holding the reserved domain
    raise TransportError(
        f"ngrok published no tunnel for port {port} within {timeout:.0f}s; see {log}."
    )


def _startup_failure(log: str, domain: str | None) -> PoliceAgentError:
    """Turn ngrok's own last words into something the user can act on."""
    said = log.lower()
    if any(marker in said for marker in _AUTH_MARKERS):
        return ConfigError(
            "ngrok is installed but not authenticated. Run this once, in your own terminal,\n"
            "with the token from https://dashboard.ngrok.com/get-started/your-authtoken:\n"
            "  ngrok config add-authtoken <your token>\n"
            "ngrok keeps it in its own config; this project never reads or holds it."
        )
    if any(marker in said for marker in _TAKEN_MARKERS):
        return ConfigError(
            f"ngrok could not claim {domain or 'a tunnel'}: it is already in use, and a free "
            f"account allows one agent session at a time. Stop the other one with\n"
            f"  pkill -f 'ngrok http'\n or at https://dashboard.ngrok.com/agents."
        )
    return TransportError(f"ngrok exited before the tunnel came up:\n{log}")


def published_url(port: int) -> str | None:
    """The URL of a tunnel already forwarding to `port`, if ngrok reports one.

    Matched on the port alone: ngrok echoes the address back as `localhost:8801`
    where we asked for 8801, and a stricter comparison would miss its own work.
    """
    urls = [
        str(one["public_url"])
        for one in _agent_tunnels()
        if one.get("public_url") and _forwards_to(one, port)
    ]
    return next((url for url in urls if url.startswith("https://")), urls[0] if urls else None)


def _forwards_to(tunnel: dict, port: int) -> bool:
    return str(tunnel.get("config", {}).get("addr", "")).endswith(f":{port}")


def _agent_tunnels() -> list[dict]:
    """What ngrok says it is publishing; an empty list when it is not running."""
    try:
        with urllib.request.urlopen(API_URL, timeout=2.0) as response:  # noqa: S310 - local API
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return []
    return [one for one in body.get("tunnels") or [] if isinstance(one, dict)]


def _tail(log: Path, lines: int = 8) -> str:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""
