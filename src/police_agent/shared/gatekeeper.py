"""Public compatibility facade for the shared outbound call gate."""

from police_agent.shared.admission import GatekeeperOverloadError
from police_agent.shared.gatekeeper_core import (
    DOS_ANOMALY_MULTIPLE,
    Gatekeeper,
    GatekeeperLockedError,
    GateLimits,
)
from police_agent.shared.quota import QuotaExceededError

__all__ = [
    "DOS_ANOMALY_MULTIPLE",
    "GateLimits",
    "Gatekeeper",
    "GatekeeperLockedError",
    "GatekeeperOverloadError",
    "QuotaExceededError",
]
