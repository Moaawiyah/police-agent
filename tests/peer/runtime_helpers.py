"""Playing one scripted sub-game against `PoliceRuntime`, split out of
test_runtime.py so every runtime test file can share the one driver.
"""

from police_agent.peer.runtime import PoliceRuntime
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport


def run_against(incoming, audit=None, **overrides):
    """Play one sub-game against a scripted thief and return (summary, transport)."""
    transport = FakeTransport(incoming=incoming, audit=audit)
    summary = PoliceRuntime(config_with(**overrides), transport).run()
    return summary, transport
