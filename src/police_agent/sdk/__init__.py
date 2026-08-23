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

from police_agent.sdk.agent import DEFAULT_REPORT_DIR, GameControls, PoliceAgentSDK
from police_agent.sdk.options import DEFAULT_CONFIG_DIR, DEFAULT_HOST, MatchOptions

# Re-exported so a front end can label which verbal-layer provider is configured
# without importing `strategy/` directly. The values stay defined in
# strategy/talk.py -- this is the boundary crossing, not a second copy, so the
# label a window shows cannot drift from what the hint writer actually does.
from police_agent.strategy.talk import DEFAULT_PROVIDER, GLM

__all__ = [
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_HOST",
    "DEFAULT_PROVIDER",
    "DEFAULT_REPORT_DIR",
    "GLM",
    "GameControls",
    "MatchOptions",
    "PoliceAgentSDK",
]
