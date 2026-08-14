"""Small, stateless pieces of `run_team_series`'s orchestration, split out to
keep `scheduler.py` within the line budget. Nothing here is monkeypatched by
name in the test suite (unlike `wait_for_thief_result`, which stays called
directly in `scheduler.py` for exactly that reason).
"""

from police_agent.exceptions import TransportError
from police_agent.report.result import scoring_from
from police_agent.report.result_parts import series_totals
from police_agent.team_sync.messages import new_message_id
from police_agent.team_sync.scheduler_fail import fail
from police_agent.team_sync.scheduler_wait import wait_for_ack, wait_for_series_start
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
        return SeriesSyncStatus(series_id=new_message_id() if start_role == POLICE else "",
                                start_role=start_role).advance(state)
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
            send_series_start(sibling, status.series_id, group_id(agent.config), total, 1, start_role)
            wait_for_sibling_ack(inboxes, sibling, status.series_id, 1)
        except TransportError as exc:
            fail(agent, store, status, f"could not announce the series to Thief: {exc}")
    elif not status.series_id:
        try:
            announced = wait_for_series_start(
                inboxes, start_role, expected_sub_game=1,
                expected_role=role_for_subgame(1, start_role), sender_role=THIEF,
            )
        except TransportError as exc:
            fail(agent, store, status, str(exc))
        status = SeriesSyncStatus(
            series_id=str(announced["series_id"]), sub_game_number=1,
            state=SeriesSyncState.WAITING, start_role=start_role,
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
                fail(agent, store, status, f"sub-game {n} settled, but handoff to Thief failed: {exc}")
        target = SeriesSyncState.READY if next_owner == POLICE else SeriesSyncState.WAITING_FOR_SIBLING
        status = status.advance(target, sub_game_number=n + 1)
        if target is SeriesSyncState.READY:
            notify_status(agent, "READY", n + 1)
    else:
        status = status.advance(SeriesSyncState.SERIES_COMPLETE, sub_game_number=n)
    store.save_status(status)
    return status


def notify_game_over(agent, summaries: list[dict]) -> None:
    """The same final `game_over` event the single-process path emits."""
    if agent.listener is None:
        return
    totals = series_totals(summaries, scoring_from(agent.config))
    agent.listener(
        {
            "type": "game_over",
            "summary": summaries[-1] if summaries else {},
            "summaries": summaries,
            "sub_game_number": len(summaries),
            "totals": totals,
        }
    )


def group_id(config) -> str:
    return str(config.get("game.group_id", "unknown-group"))


def notify_status(agent, status: str, sub_game_number: int) -> None:
    """A team_sync-kind event for statuses no `PoliceRuntime` event covers --
    chiefly the even sub-games, which this process never plays itself."""
    if agent.listener is not None:
        agent.listener({"type": "team_sync", "status": status, "state": status,
                        "sub_game_number": sub_game_number})


def start_role(config, settings) -> str:
    value = config.get("team_sync.start_role")
    if value is None:
        value = config.get("start_role", config.get("game.start_role", settings.get("start_role", "police")))
    if value not in (POLICE, THIEF):
        raise ValueError("team_sync.start_role must be 'police' or 'thief'")
    return value


def send_series_start(client, series_id, game_id, total, first, start_role):
    next_role = role_for_subgame(first, start_role)
    try:
        return client.send_series_start(series_id, game_id, total, first,
                                       start_role=start_role, next_role=next_role)
    except TypeError:
        return client.send_series_start(series_id, game_id, total, first)


def send_handoff(client, series_id, completed, next_subgame, start_role, next_role):
    try:
        return client.send_handoff(series_id, completed, next_subgame,
                                   start_role=start_role, next_role=next_role)
    except TypeError:
        return client.send_handoff(series_id, completed, next_subgame)


def wait_for_sibling_ack(inboxes, client, series_id: str, sub_game_number: int) -> None:
    """Real clients expose the outbound message id; old test doubles do not."""
    message_id = getattr(client, "last_message_id", "")
    if message_id and hasattr(inboxes, "acks"):
        wait_for_ack(inboxes, series_id, message_id, sub_game_number)
