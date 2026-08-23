"""Reproducible parameter experiments for the police agent (specification 17.5).

Deliberately outside `src/police_agent/`. Two reasons, and both matter:

* This is research tooling, not part of the shipped agent. Nothing under
  `src/` imports it, so a sweep cannot change how a real match is played.
* The sweeps need an opponent, and CLAUDE.md forbids thief agent logic in this
  repository. `evader.py` holds a deliberately trivial synthetic evader -- a
  research fixture that generates trajectories and scent, never a thief agent
  and never a peer. It is a data generator standing in for one, in the same
  spirit as a test double, and it is kept here rather than in `src/` so nothing
  can mistake it for a shipped component.

The measured results and the figures they produce are written up in
`docs/RESEARCH.md`; `notebooks/sensitivity.ipynb` is the interactive version.
Run `uv run python -m research` to regenerate every figure from scratch.
"""

BOARD_SIZE = 7
POLICE_START = (0, 0)
THIEF_START = (3, 3)
MAX_STEPS = 35
MAX_BARRIERS = 14

# The agreed pheromone terms from config/police/game.json, spelled out so a
# sweep records the constants it actually ran under rather than silently
# following a config edit.
SCENT_GRID_SIZE = 5
SCENT_DECAY = 0.1
SCENT_EMIT_INTENSITY = 0.9
SCENT_MIN_CENTER = 0.5
