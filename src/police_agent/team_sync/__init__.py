"""team_sync: local coordination between this repo's Police process and the
independent, separately-owned Thief sibling process on the same machine.

Two OS processes, no shared memory (CLAUDE.md), talking only over a small
localhost-bound FastMCP channel (`coordinator.py`/`client.py`), signed with
an HMAC-SHA256 shared secret (`security.py`) as defense-in-depth alongside
the `127.0.0.1` bind. `scheduler.run_team_series(agent)` is the entry point
`sdk/series.py::play_series()` delegates to when `team_sync.enabled` is set;
every other symbol here is a supporting piece of that one loop.
"""

from police_agent.team_sync.scheduler import run_team_series
from police_agent.team_sync.state import SeriesSyncState, SeriesSyncStatus, role_for_subgame

__all__ = ["SeriesSyncState", "SeriesSyncStatus", "role_for_subgame", "run_team_series"]
