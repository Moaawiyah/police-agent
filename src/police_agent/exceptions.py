"""The police agent's exception hierarchy.

One root class keeps the top-level runner honest: it can catch every error this
agent raises on purpose without also swallowing genuine bugs such as TypeError.
That distinction matters here because the specification treats a crashed peer as
a *technical loss*, so an unhandled failure has a score attached to it.
"""


class PoliceAgentError(Exception):
    """Base class for every error this agent raises deliberately."""


class ConfigError(PoliceAgentError):
    """Missing, malformed, or unsupported configuration."""


class TransportError(PoliceAgentError):
    """The peer-to-peer link failed: opponent unreachable, or no reply in time."""


class ProtocolError(PoliceAgentError):
    """A wire message arrived, but its shape or contents violate the protocol."""


class MoveError(PoliceAgentError):
    """An illegal or invalid game move."""


class CryptoError(PoliceAgentError):
    """A commitment did not match what was revealed, or terms were not signed."""
