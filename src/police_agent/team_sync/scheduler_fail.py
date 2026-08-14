"""Graceful degradation for `scheduler.py`: a stuck or unreachable sibling
must leave a visible trace -- a persisted ERROR status and a listener event
-- never just an uncaught traceback with no clue what to check.

Split out of `scheduler.py` to keep it under the project's line budget.
"""

from police_agent.exceptions import TransportError
from police_agent.team_sync.state import SeriesSyncState

__all__ = ["fail"]


def fail(agent, store, status, message: str) -> None:
    """Persist `status` as ERROR, notify the listener, then raise.

    Never swallows the failure: the caller still sees an exception (a CLI run
    exits non-zero with this exact message; the GUI's existing worker-thread
    handler already turns any uncaught exception into an `error` event), but
    now there is also a status file on disk and a clear reason recorded,
    instead of a bare stack trace pointing nowhere in particular.
    """
    failed = status.advance(SeriesSyncState.ERROR)
    store.save_status(failed)
    if agent.listener is not None:
        agent.listener({"type": "team_sync", "status": f"ERROR - {message}",
                        "state": "SYNC_ERROR"})
    raise TransportError(message)
