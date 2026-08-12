"""Real inbound enforcement for this peer's own mailbox (spec ch. 9.3.1).

mcp_server.py's tools deliberately do no reasoning -- they queue and return.
This is the interception point FastMCP provides for exactly the policy
rate_limit.py's own docstring already anticipated: the same DosDetector class
that locks the outbound door can, here, do more than just report.
"""

from fastmcp.server.middleware import Middleware
from mcp import McpError
from mcp.types import ErrorData

from police_agent.shared.rate_limit import DosDetector


class InboundDosError(McpError):
    """Raised from middleware, not returned -- matches fastmcp's own built-in
    rate_limiting.py exactly, so a rejection reaches the opponent's
    McpTransport as a clean typed error, not a hang or a generic 500."""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorData(code=-32000, message=message))


class InboundDosGuard(Middleware):
    """Rejects a tool call once the shared inbound detector has tripped.

    Applied uniformly across all 4 tools, deliberately not per-tool: a flood
    aimed at negotiate/submit_audit is exactly as much a flood as one aimed
    at receive_turn, and splitting one shared budget four ways would only
    make each individual ceiling easier to trip by accident.
    """

    def __init__(self, detector: DosDetector) -> None:
        self._detector = detector

    async def on_call_tool(self, context, call_next):
        if not self._detector.record():
            raise InboundDosError(
                f"inbound rate exceeded {self._detector.limit_per_minute:.0f}/min "
                f"on {context.message.name!r} -- this peer is locked"
            )
        return await call_next(context)
