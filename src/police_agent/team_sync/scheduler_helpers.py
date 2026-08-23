"""Small, stateless pieces of `run_team_series`'s orchestration, split out to
keep `scheduler.py` within the line budget. Nothing here is monkeypatched by
name in the test suite (unlike `wait_for_thief_result`, which stays called
directly in `scheduler.py` for exactly that reason).

What decides *when* the sibling is written to lives here; the writes themselves
are in `scheduler_send.py`. The reporting helpers (`notify_game_over`,
`group_id`, `notify_status`) moved to `scheduler_status.py` to keep this file
inside the same budget, and are re-imported below so `scheduler.py`'s
`helpers.*` calls do not need to know they moved. `start_role` moved there too
but is *not* re-imported here: it would collide with the `start_role`
parameter every function below takes, so `scheduler.py` calls it on
`scheduler_status` directly instead.
"""

from police_agent.exceptions import TransportError
from police_agent.team_sync.messages import new_message_id
from police_agent.team_sync.scheduler_fail import fail
from police_agent.team_sync.scheduler_send import (
    send_handoff,
    send_series_start,
    wait_for_sibling_ack,
)
from police_agent.team_sync.scheduler_status import (  # noqa: F401 - re-exported for scheduler.py
    group_id,
    notify_game_over,
    notify_status,
)
from police_agent.team_sync.scheduler_wait import wait_for_series_start
from police_agent.team_sync.state import (
    POLICE,
    THIEF,
    SeriesSyncState,
    SeriesSyncStatus,
    role_for_subgame,
)


def resume_or_start(store, start_role: str) -> SeriesSyncStatus:
    """The persisted position, normalized back to READY (a resumed status
    cannot be trusted mid-flight) -- or a fresh series."""
    persisted = store.load_status()
    if persisted is None:
        state = SeriesSyncState.READY if start_role == POLICE else SeriesSyncState.WAITING
        return SeriesSyncStatus(
            series_id=new_message_id() if start_role == POLICE else "", start_role=start_role
        ).advance(state)
    return SeriesSyncStatus(
        series_id=persisted.series_id,
        sub_game_number=persisted.sub_game_number,
        state=SeriesSyncState.READY,
        updated_at=persisted.updated_at,
        start_role=start_role,
    )


def announce_opening(agent, store, status, start_role, sibling, inboxes, total):
    """Sub-game 1's opening negotiation: Police announces it (owns it), or
    waits for Thief's own announcement (Thief owns it). Returns `status`."""
    if status.sub_game_number <= 1 and start_role == POLICE:
        try:
            # The sibling must start its Thief runtime for G1 too; Police is
            # the owner of G1, but the two fixed-role runtimes still negotiate
            # and audit the same live sub-game.
            send_series_start(
                sibling, status.series_id, group_id(agent.config), total, 1, start_role
            )
            wait_for_sibling_ack(inboxes, sibling, status.series_id, 1)
        except TransportError as exc:
            fail(agent, store, status, f"could not announce the series to Thief: {exc}")
    elif not status.series_id:
        try:
            announced = wait_for_series_start(
                inboxes,
                start_role,
                expected_sub_game=1,
                expected_role=role_for_subgame(1, start_role),
                sender_role=THIEF,
            )
        except TransportError as exc:
            fail(agent, store, status, str(exc))
        status = SeriesSyncStatus(
            series_id=str(announced["series_id"]),
            sub_game_number=1,
            state=SeriesSyncState.WAITING,
            start_role=start_role,
        )
        store.save_status(status)
        if announced.get("message_id") and hasattr(sibling, "send_ack"):
            sibling.send_ack(status.series_id, announced["message_id"], 1)
    return status


def advance_to_next(agent, store, sibling, inboxes, status, start_role, n, total, police_turn):
    """After sub-game `n` settles: hand off to the next owner (if Police just
    settled its own), or mark the series complete. Returns `status`."""
    if n < total:
        next_owner = role_for_subgame(n + 1, start_role)
        if police_turn:
            try:
                send_handoff(sibling, status.series_id, n, n + 1, start_role, next_owner)
                wait_for_sibling_ack(inboxes, sibling, status.series_id, n + 1)
            except TransportError as exc:
                fail(
                    agent,
                    store,
                    status,
                    f"sub-game {n} settled, but handoff to Thief failed: {exc}",
                )
        target = (
            SeriesSyncState.READY if next_owner == POLICE else SeriesSyncState.WAITING_FOR_SIBLING
        )
        status = status.advance(target, sub_game_number=n + 1)
        if target is SeriesSyncState.READY:
            notify_status(agent, "READY", n + 1)
    else:
        status = status.advance(SeriesSyncState.SERIES_COMPLETE, sub_game_number=n)
    store.save_status(status)
    return status
