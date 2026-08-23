"""The team_sync state machine's legal-transition table, split out of
`state.py` to keep it inside the project's 150-line budget.
"""

from police_agent.team_sync.state import SeriesSyncState

# Legal forward transitions: every value in the set is a state `advance` may
# move *to* from the key. Kept explicit so an out-of-order or duplicated
# event fails loudly (`ValueError`) instead of silently overwriting progress.
_TRANSITIONS: dict[SeriesSyncState, frozenset[SeriesSyncState]] = {
    SeriesSyncState.IDLE: frozenset({SeriesSyncState.READY, SeriesSyncState.WAITING}),
    SeriesSyncState.READY: frozenset(
        {
            SeriesSyncState.NEGOTIATING,
            SeriesSyncState.WAITING_FOR_SIBLING,
            SeriesSyncState.PLAYING,
            SeriesSyncState.SYNC_ERROR,
            SeriesSyncState.ERROR,
        }
    ),
    SeriesSyncState.WAITING: frozenset(
        {
            SeriesSyncState.READY,
            SeriesSyncState.WAITING_FOR_SIBLING,
            SeriesSyncState.NEGOTIATING,
            SeriesSyncState.SYNC_ERROR,
            SeriesSyncState.ERROR,
        }
    ),
    SeriesSyncState.NEGOTIATING: frozenset(
        {SeriesSyncState.PLAYING, SeriesSyncState.SYNC_ERROR, SeriesSyncState.ERROR}
    ),
    SeriesSyncState.PLAYING: frozenset(
        {
            SeriesSyncState.AUDITING,
            SeriesSyncState.SETTLED,
            SeriesSyncState.SYNC_ERROR,
            SeriesSyncState.ERROR,
        }
    ),
    SeriesSyncState.AUDITING: frozenset(
        {SeriesSyncState.SETTLED, SeriesSyncState.SYNC_ERROR, SeriesSyncState.ERROR}
    ),
    SeriesSyncState.SETTLED: frozenset(
        {
            SeriesSyncState.WAITING_FOR_SIBLING,
            SeriesSyncState.READY,
            SeriesSyncState.SERIES_COMPLETE,
            SeriesSyncState.SYNC_ERROR,
            SeriesSyncState.ERROR,
        }
    ),
    SeriesSyncState.WAITING_FOR_SIBLING: frozenset(
        {
            SeriesSyncState.READY,
            SeriesSyncState.SETTLED,
            SeriesSyncState.SYNC_ERROR,
            SeriesSyncState.ERROR,
        }
    ),
    SeriesSyncState.SERIES_COMPLETE: frozenset(),
    SeriesSyncState.SYNC_ERROR: frozenset(),
    SeriesSyncState.ERROR: frozenset(),
}


def can_transition(current: SeriesSyncState, target: SeriesSyncState) -> bool:
    """Whether moving from `current` to `target` is a legal step."""
    return target in _TRANSITIONS.get(current, frozenset())
