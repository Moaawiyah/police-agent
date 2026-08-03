"""The public address the opposing team can actually reach: an ngrok tunnel.

Appendix He rule 10 makes tunnelling mandatory, and ch. 2.4.1 says why: both
peers sit behind NAT, so a `network.opponent_url` naming 127.0.0.1 can only
describe an opponent on this same machine. ngrok gives one public URL that its
edge forwards to the port `mcp_server.py` already bound, so `infra/` gains a hop
and nothing above it learns there was one.

The authtoken is never touched here: ngrok reads it from its own config file,
written once by `ngrok config add-authtoken`, so this module has no token
parameter, nothing to read from the environment, and nothing to leak (rule 39).

Starting the process, polling its agent API and reading its own diagnostics on
failure is the other half of this, in `ngrok_agent.py` -- kept apart so both
files stay under the project's 150-line rule. A missing binary, an
unauthenticated ngrok and a domain someone else holds are all wrong on *this*
machine, so they raise `ConfigError` there exactly as a taken port does in
`mcp_server.py`. A tunnel that starts and never comes up is the public link
itself failing, hence `TransportError` -- and by ch. 2.4.1 that deadlocks the
opponent's turn timing, so it is worth saying loudly and at once.
"""

import atexit
import subprocess
from pathlib import Path

from police_agent.infra.ngrok_agent import launch

STARTUP_TIMEOUT = 30.0
_SHUTDOWN_GRACE = 5.0


class NgrokTunnel:
    """A public address for this peer's MCP server, and the process holding it."""

    def __init__(self, public_url: str, process=None, log: Path | None = None) -> None:
        self.public_url = public_url
        self._process = process
        self._log = log

    @property
    def mcp_url(self) -> str:
        """The address an opponent dials: ngrok's origin plus our /mcp mount.

        Handing over the bare origin is the mistake this property exists to stop.
        """
        return f"{self.public_url.rstrip('/')}/mcp"

    def close(self) -> None:
        """Stop ngrok, once. An adopted tunnel is left alone: it is not ours.

        A daemon thread dies with its process, which is how `mcp_server.py` gets
        away with never stopping its server; a child process does not, and this
        one holds a reserved domain while it lives, so the next run would be
        refused that domain by ngrok's edge. Hence an explicit shutdown, filed
        with atexit too: the exits that matter have no `finally` around them.
        """
        process, self._process = self._process, None
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=_SHUTDOWN_GRACE)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._log is not None:
            self._log.unlink(missing_ok=True)


def open_tunnel(port: int, domain: str | None = None, *, timeout: float = STARTUP_TIMEOUT):
    """Publish `port` on the public internet and return the live tunnel.

    Blocks until ngrok reports a URL: one that is not up yet looks exactly like
    one that never will be, and the caller is about to print this address for a
    human to hand to the other team.
    """
    public_url, process, log = launch(port, domain, timeout)
    tunnel = NgrokTunnel(public_url, process, log)
    if process is not None:
        # An adopted tunnel has no process of ours to register: closing it would
        # kill an agent this peer never started.
        atexit.register(tunnel.close)
    return tunnel
