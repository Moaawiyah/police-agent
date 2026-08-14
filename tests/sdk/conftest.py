"""Shared SDK test helpers, split out so no test_agent_*.py file needs to
import from another -- each stays independently runnable and under 150 lines.
"""

from police_agent.sdk import PoliceAgentSDK
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport

NETWORKED = {"network__my_port": 8801, "network__opponent_url": "http://127.0.0.1:8802/mcp"}
UNWIRED = object()  # distinguishes "no transport given" from "inject None"


def agent_with(transport=UNWIRED, listener=None, options=None, **overrides) -> PoliceAgentSDK:
    """An SDK on the agreed terms, wired to a test double instead of a socket."""
    return PoliceAgentSDK(
        options,
        config=config_with(**{**NETWORKED, **overrides}),
        transport=FakeTransport() if transport is UNWIRED else transport,
        listener=listener,
    )


def _forbidden(what: str):
    def fail(*args, **kwargs):
        raise AssertionError(what)

    return fail


def record_wiring(monkeypatch) -> tuple[list, list]:
    """Replace the socket-touching constructors with recorders, and ban ngrok."""
    opened: list = []
    dialled: list = []

    def start(role, host, port, dos_limit_per_minute=30.0):
        opened.append((role, host, port))
        return "inboxes"

    def transport(url, inboxes, **timeouts):
        dialled.append((url, inboxes, FakeTransport(), timeouts))
        return dialled[-1][2]

    monkeypatch.setattr("police_agent.sdk.agent_connection.start_peer_server", start)
    monkeypatch.setattr("police_agent.sdk.agent_connection.McpTransport", transport)
    # Tunnelling is opt-in, so every test using this helper also proves that a
    # default run starts no child process and publishes nothing to the internet.
    monkeypatch.setattr(
        "police_agent.sdk.agent_connection.open_tunnel", _forbidden("started ngrok")
    )
    return opened, dialled
