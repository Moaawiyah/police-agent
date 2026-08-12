"""Component wiring for `PoliceRuntime.__init__`, split out to keep the
constructor -- and the file it lives in -- under the project's line budget.
"""

import time

from police_agent.domain.own_state import OwnGameState
from police_agent.domain.rules import GameRules
from police_agent.domain.scent import ScentField
from police_agent.peer.control_link import ControlLink
from police_agent.peer.controls import GameControls
from police_agent.peer.sealing import now_iso
from police_agent.peer.step_zero import sealed_step_zero
from police_agent.peer.terms import validate_agreement
from police_agent.peer.turn_handler import TurnHandler
from police_agent.peer.watchdog import Watchdog
from police_agent.shared.gatekeeper import Gatekeeper
from police_agent.shared.tokens import TokenLedger
from police_agent.strategy import resolve_brain
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.bluff import resolve_bluff_analyst
from police_agent.strategy.talk import resolve_hint_writer


def wire(runtime, config, transport, sub_game_number, league, **components) -> None:
    """Build every collaborator `PoliceRuntime` needs and set it as an
    attribute of `runtime`, in the same order `__init__` used to build them
    in-line: later attributes are free to depend on earlier ones (e.g. the
    gatekeeper the hint writer and analyst are both wired through)."""
    # Validated before anything else: a missing agreed term is far cheaper to
    # discover here than three turns into a match against another group.
    runtime.terms = validate_agreement(config)
    runtime.config = config
    runtime.sub_game_number = (
        sub_game_number if sub_game_number is not None else config.get("game.sub_game_number", 1)
    )
    runtime.transport = transport
    runtime.league = league

    size = runtime.terms["board_size"]
    runtime.state = OwnGameState(tuple(runtime.terms["cop_start"]), size)
    # survival_threshold is deliberately not a signed term (matching the
    # reference's term list is what lets the handshake succeed), but still
    # comes from the shared game.json, so both peers agree in practice.
    runtime.rules = GameRules(runtime.terms["max_steps"], config.require("rules.survival_threshold"))
    runtime.barriers_max = runtime.terms["barriers_max"]

    # One gate and one ledger for the whole match. Every outbound call to
    # somebody else's service leaves through the gate (Appendix He 28) and
    # every model call this peer makes lands in the tally (Appendix He 54);
    # building them here is what stops the two halves of the verbal layer
    # from quietly running two rate limiters at twice the agreed rate.
    runtime.gatekeeper = Gatekeeper.from_config(config)
    runtime.tokens = TokenLedger()
    # The real, enforcing detector lives on the transport's own inboxes
    # (infra/mcp_guard.py runs it on the server's daemon thread, before a
    # flood ever reaches this loop); reading it through here is what lets
    # the match summary report on the same instance that did the guarding.
    runtime.inbound_dos = transport.inbound_dos

    runtime.threat = components["threat"] or BeliefGrid.from_config(runtime.terms, config)
    runtime.brain = components["brain"] or resolve_brain(config)
    runtime.scent = components["scent"] or ScentField.from_terms(runtime.terms)
    runtime.hint_writer = components["hint_writer"] or resolve_hint_writer(
        config, gate=runtime.gatekeeper, ledger=runtime.tokens
    )
    runtime.analyst = components["analyst"] or resolve_bluff_analyst(
        config, runtime.gatekeeper, runtime.tokens
    )
    runtime.handler = TurnHandler(runtime.state, runtime.threat, runtime.rules, runtime.analyst)

    runtime._listener = components["listener"]
    runtime.controls = components["controls"] or GameControls()
    # Fresh per sub-game, started/stopped around _turn_loop() only: a
    # heartbeat baseline from a possibly-long gap since the last sub-game
    # would be meaningless carried over.
    runtime.watchdog = components["watchdog"] or Watchdog.from_config(
        config, runtime.controls, on_trip=runtime._set_abort_reason
    )
    runtime.abort_reason: str | None = None
    # Opt-in bidirectional signalling (enable/status/restart/quit). Advisory
    # only -- see control_link.py -- so building it here, unconditionally,
    # commits this peer to nothing until the GUI's checkbox turns it on.
    runtime.link = components["link"] or ControlLink(
        "police", runtime.transport, runtime.controls, runtime.notify
    )
    # The declaration heads the log, sealed before anything is played, so its
    # digest can go out with the handshake below (Appendix He 24/53).
    runtime.records: list[dict] = [sealed_step_zero(config, runtime.sub_game_number)]
    runtime.disputes: list[str] = []
    runtime.belief_log: list[dict] = []  # one entry per Bayes-filter update
    runtime.peer_identity: dict = {}
    runtime.started_at = now_iso()
    runtime.started_monotonic = time.monotonic()
    runtime._result: tuple[str, str | None] | None = None
