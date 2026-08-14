"""team_sync's orchestration loop for two fixed-role peer processes.

Both processes participate in every MCP sub-game.  `role_for_subgame` only
decides which process owns the READY/handoff and settled-result ledger for
that sub-game; it never removes the other role from the live game flow.

`wait_for_thief_result` stays called directly here rather than in
`scheduler_helpers.py` (everything else this loop does besides play/settle a
sub-game): the test suite monkeypatches it by name on this module.
"""

import contextlib

from police_agent.exceptions import TransportError
from police_agent.peer.series import series_count
from police_agent.report.writer import report_dir
from police_agent.sdk import GameControls
from police_agent.team_sync import client as ts_client
from police_agent.team_sync import config as ts_config
from police_agent.team_sync import coordinator as ts_coordinator
from police_agent.team_sync import import_adapter
from police_agent.team_sync import scheduler_helpers as helpers
from police_agent.team_sync.resume import backfill_missing_summaries
from police_agent.team_sync.scheduler_fail import fail
from police_agent.team_sync.scheduler_wait import wait_for_handoff, wait_for_thief_result
from police_agent.team_sync.security import secret_from_env
from police_agent.team_sync.state import POLICE, SeriesSyncState, role_for_subgame
from police_agent.team_sync.store import TeamSyncStore

__all__ = ["run_team_series"]


def run_team_series(agent, base: str = "logs") -> list[dict]:
    """Run all six live sub-games, importing Thief-owned settled results."""
    settings = ts_config.settings(agent.config)
    start_role = helpers.start_role(agent.config, settings)
    secret = secret_from_env()
    store = TeamSyncStore(report_dir(base, helpers.group_id(agent.config)) / "team_sync")
    fresh_start = agent._team_sync_fresh_start
    if fresh_start:
        store.reset_series()
        agent._team_sync_fresh_start = False
    status = helpers.resume_or_start(store, start_role)
    coordinator = agent._team_sync_coordinator
    if coordinator is None or coordinator[1] is None or not coordinator[1].is_alive():
        coordinator = ts_coordinator.start_coordinator(
            settings["host"], settings["port"], secret, status.to_dict
        )
        agent._team_sync_coordinator = coordinator
    inboxes, _thread = coordinator
    if fresh_start:
        inboxes.clear()
    sibling = ts_client.TeamSyncClient(settings["sibling_url"], secret)
    agent.connect()
    controls = agent.controls or GameControls()

    total = series_count(agent.config)
    summaries: list[dict] = [{}] * total
    if status.sub_game_number > 1:
        backfill_missing_summaries(agent, base, helpers.group_id(agent.config), summaries)
    status = helpers.announce_opening(agent, store, status, start_role, sibling, inboxes, total)

    for n in range(max(status.sub_game_number, 1), total + 1):
        police_turn = role_for_subgame(n, start_role) == POLICE
        if status.state in (SeriesSyncState.WAITING, SeriesSyncState.WAITING_FOR_SIBLING,
                            SeriesSyncState.SETTLED):
            status = status.advance(SeriesSyncState.READY, n)
        helpers.notify_status(agent, "READY" if police_turn else "WAITING", n)
        status = status.advance(SeriesSyncState.PLAYING, n)
        helpers.notify_status(agent, "PLAYING" if police_turn else "WAITING", n)
        store.save_status(status)

        # The fixed Police runtime must be present for every sub-game, even
        # when Thief owns the series handoff/result for this number.
        local_summary = agent.build_runtime(n, controls=controls).run()
        status = status.advance(SeriesSyncState.AUDITING, n)
        helpers.notify_status(agent, "AUDITING", n)

        if police_turn:
            summary = local_summary
            paths = agent.write_artifacts(summary, base)
            import_adapter.maybe_email_final_report(agent, paths, summary, store)
        else:
            try:
                message = wait_for_thief_result(inboxes, status.series_id, n)
            except TransportError as exc:
                fail(agent, store, status, str(exc))
            # Thief's complete settled payload is the ledger copy for its
            # owned sub-game; local Police runtime state is never exchanged.
            summary = import_adapter.import_and_persist(message, agent, base, store)
            if n < total and hasattr(inboxes, "handoff"):
                handoff = wait_for_handoff(inboxes, status.series_id, n + 1)
                if handoff.get("message_id") and hasattr(sibling, "send_ack"):
                    sibling.send_ack(status.series_id, handoff["message_id"], n + 1)

        status = status.advance(SeriesSyncState.SETTLED, n)
        helpers.notify_status(agent, "SETTLED", n)
        summaries[n - 1] = summary
        status = helpers.advance_to_next(
            agent, store, sibling, inboxes, status, start_role, n, total, police_turn
        )

    helpers.notify_status(agent, "SERIES_COMPLETE", total)
    helpers.notify_game_over(agent, summaries)
    if hasattr(sibling, "send_series_complete"):
        # The final report is already persisted and email-gated locally; a
        # notification failure must not create a second report.
        with contextlib.suppress(TransportError):
            sibling.send_series_complete(status.series_id)
    return summaries
