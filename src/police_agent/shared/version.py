"""Version tracking for the code and for the config schema it understands.

Two versions, because they move independently. `CODE_VERSION` is this agent;
`SUPPORTED_CONFIG_VERSIONS` is which private `game.toml` layouts it can read.
The agreed `game.json` carries its own `schema_version` and is not listed here:
that one is negotiated with the opponent, not chosen by us.

Shown in the window's About dialog, which is the point of having it in one
place -- a version reported from a GUI string literal would drift the first time
anything else was released.
"""

CODE_VERSION = "1.00"
SUPPORTED_CONFIG_VERSIONS = ("1.10",)

PROJECT_TITLE = "Police Agent - P2P Cops-and-Robbers"
REPOSITORY_URL = "https://github.com/Moaawiyah/police-agent"
THIEF_REPOSITORY_URL = "https://github.com/Moaawiyah/Ai_thief"
