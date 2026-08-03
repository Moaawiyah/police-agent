"""The SDK layer: the police agent's public API.

Every capability this repository has is reachable through `PoliceAgentSDK`.
Front ends -- the `police-agent` CLI today, the step-8 GUI and replay viewer
next -- parse their own input, call these methods and render what comes back.
None of them constructs a runtime, resolves a port or loads a config file
itself, and none of them may reach past this layer into `peer/` or `domain/`.

The rule is worth stating as a rule because the alternative is so easy to drift
into: the CLI already knew how to build a transport, so the GUI would have
learned it too, and the two would have gone out of step the first time a
constructor changed. One composition root, imported by both, cannot.

This layer holds no game rules of its own. It decides *which* objects get built
and with what settings; how the game is played stays in `domain/` and `peer/`.
"""

from police_agent.sdk.agent import PoliceAgentSDK
from police_agent.sdk.options import DEFAULT_CONFIG_DIR, DEFAULT_HOST, MatchOptions

__all__ = [
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_HOST",
    "MatchOptions",
    "PoliceAgentSDK",
]
