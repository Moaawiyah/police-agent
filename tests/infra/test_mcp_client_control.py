"""send_control: the outbound half of the bidirectional control channel.

Split from test_mcp_client.py to keep both files within the 150-line rule.
"""

from police_agent.infra.mcp_client import McpTransport
from police_agent.infra.mcp_server import PeerInboxes
from tests.infra.test_mcp_client import UNREACHABLE, Recorder


def transport(**overrides) -> McpTransport:
    settings = {"connect_timeout": 0.05, "retry_interval": 0.01, "reply_timeout": 0.05}
    return McpTransport(UNREACHABLE, PeerInboxes(), **(settings | overrides))


def test_send_control_targets_receive_control():
    link = transport()
    link._call = Recorder()
    link.send_control({"kind": "enable", "sender": "police"})
    assert link._call.calls == [
        ("receive_control", {"message": {"kind": "enable", "sender": "police"}})
    ]


def test_send_control_is_best_effort_and_never_raises():
    """Control messages are advisory only -- a departed or slow opponent must
    never turn into a game-stalling exception."""
    link = transport()

    def boom(*args, **kwargs):
        raise OSError("connection refused")

    link._call = boom
    link.send_control({"kind": "quit", "sender": "police"})  # must not raise
