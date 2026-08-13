"""team_sync's orchestration loop: play only Police's own sub-games, import
the sibling Thief process's, alternating strictly by `role_for_subgame`.

Only entered when config `team_sync.enabled` is true (see `sdk/series.py`);
the single-process `peer/series.py::run_series` path is untouched.
"""

from police_agent.exceptions import TransportError
from police_agent.peer.controls import GameControls
from police_agent.peer.runtime import PoliceRuntime
from police_agent.peer.series import series_count
from police_agent.report.result import scoring_from
from police_agent.report.result_parts import series_totals
from police_agent.report.writer import report_dir
from police_agent.sdk.series import series_listener
from police_agent.team_sync import client as ts_client
from police_agent.team_sync import config as ts_config
from police_agent.team_sync import coordinator as ts_coordinator
from police_agent.team_sync import import_adapter
from police_agent.team_sync.messages import new_message_id
from police_agent.team_sync.resume import backfill_missing_summaries
from police_agent.team_sync.scheduler_fail import fail
from police_agent.team_sync.scheduler_wait import wait_for_thief_result
from police_agent.team_sync.security import secret_from_env
from police_agent.team_sync.state import (
    POLICE,
    THIEF,
    SeriesSyncState,
    SeriesSyncStatus,
    role_for_subgame,
)
from police_agent.team_sync.store import TeamSyncStore


def run_team_series(agent, base: str = "logs") -> list[dict]:
    """Play the agreed series, alternating Police's own sub-games with the
    sibling Thief process's, and return every sub-game's summary in order."""
    settings = ts_config.settings(agent.config)
    secret = secret_from_env()
    store = TeamSyncStore(report_dir(base, _group_id(agent.config)) / "team_sync")
    status = _resume_or_start(store)
    inboxes, _thread = ts_coordinator.start_coordinator(
        settings["host"], settings["port"], secret, status.to_dict
    )
    sibling = ts_client.TeamSyncClient(settings["sibling_url"], secret)
    transport = agent.connect()
    police_kwargs = {
        "listener": series_listener(agent),
        "controls": agent.controls or GameControls(),
        "league": agent.options.league,
    }

    total = series_count(agent.config)
    summaries: list[dict] = [{}] * total
    if status.sub_game_number > 1:
        backfill_missing_summaries(agent, base, _group_id(agent.config), summaries)
    if status.sub_game_number <= 1:
        first_sibling_subgame = _first_role_subgame(total, THIEF)
        if first_sibling_subgame:
            try:
                sibling.send_series_start(
                    status.series_id, _group_id(agent.config), total, first_sibling_subgame
                )
            except TransportError as exc:
                fail(agent, store, status, f"could not announce the series to Thief: {exc}")

    for n in range(max(status.sub_game_number, 1), total + 1):
        police_turn = role_for_subgame(n) == POLICE
        status = status.advance(
            SeriesSyncState.PLAYING if police_turn else SeriesSyncState.WAITING_FOR_SIBLING
        )
        store.save_status(status)
        if police_turn:
            runtime = PoliceRuntime(agent.config, transport, sub_game_number=n, **police_kwargs)
            summary = runtime.run()
            paths = agent.write_artifacts(summary, base)
            import_adapter.maybe_email_final_report(agent, paths, summary, store)
            try:
                sibling.send_handoff(status.series_id, n, n + 1)
            except TransportError as exc:
                fail(agent, store, status, f"sub-game {n} settled, but handoff to Thief failed: {exc}")
        else:
            _notify_status(agent, "waiting_for_sibling", n)
            try:
                message = wait_for_thief_result(inboxes, status.series_id, n)
            except TransportError as exc:
                fail(agent, store, status, str(exc))
            # No separate ack round-trip: the sibling's `subgame_result` tool
            # call already gets `{"ok": True}` back synchronously (Thief has
            # no `ack` tool to receive one, and never waits for it either).
            summary = import_adapter.import_and_persist(message, agent, base, store)
            _notify_status(agent, "subgame_settled", n)
        summaries[n - 1] = summary
        status = status.advance(SeriesSyncState.SETTLED)
        target = SeriesSyncState.SERIES_COMPLETE if n == total else SeriesSyncState.READY
        status = status.advance(target, sub_game_number=n + 1)
        store.save_status(status)

    _notify_game_over(agent, summaries)
    return summaries


def _resume_or_start(store: TeamSyncStore) -> SeriesSyncStatus:
    """The persisted position, normalized back to READY (a resumed status
    cannot be trusted mid-flight) -- or a fresh series."""
    persisted = store.load_status()
    if persisted is None:
        return SeriesSyncStatus(series_id=new_message_id()).advance(SeriesSyncState.READY)
    return SeriesSyncStatus(
        series_id=persisted.series_id,
        sub_game_number=persisted.sub_game_number,
        state=SeriesSyncState.READY,
        updated_at=persisted.updated_at,
    )


def _notify_game_over(agent, summaries: list[dict]) -> None:
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


def _group_id(config) -> str:
    return str(config.get("game.group_id", "unknown-group"))


def _first_role_subgame(total: int, role: str) -> int:
    """The lowest sub-game number `role` owns, or 0 if it owns none at all
    (only possible for a very short series -- normally this is 2)."""
    return next((n for n in range(1, total + 1) if role_for_subgame(n) == role), 0)


def _notify_status(agent, status: str, sub_game_number: int) -> None:
    """A team_sync-kind event for statuses no `PoliceRuntime` event covers --
    chiefly the even sub-games, which this process never plays itself."""
    if agent.listener is not None:
        agent.listener({"type": "team_sync", "status": status, "sub_game_number": sub_game_number})
