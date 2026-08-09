"""Turn-loop operations delegated by :class:`PoliceRuntime`."""

from police_agent.domain.rules import ABORTED, CAPTURE, SURVIVAL, TECHNICAL_LOSS, TIMEOUT
from police_agent.peer import runtime_control
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.reference_v3 import refuse_turn
from police_agent.peer.turn_sender import take_turn
from police_agent.peer.view import belief_matrix, snapshot


def notify(runtime, event: dict) -> None:
    if runtime._listener is not None:
        runtime._listener(
            {**event, "sub_game_number": runtime.sub_game_number, "view": snapshot(runtime)}
        )


def turn_loop(runtime) -> None:
    timeout = runtime._turn_timeout()
    while runtime._result is None:
        # Pumped once per round rather than continuously: a restart or quit is
        # noticed at the same cadence a real opponent's turn would arrive at,
        # which is the same responsiveness the reference's own design accepts.
        runtime_control.pump(runtime, runtime_control.WAITING)
        runtime_control.check(runtime)  # may raise RestartRequested
        if runtime._result is not None:
            return
        runtime.controls.wait_if_paused()
        if runtime.controls.stopped:
            runtime._result = (ABORTED, None)
            return
        incoming = runtime.transport.poll_turn(timeout)
        if incoming is None:
            runtime._result = (TECHNICAL_LOSS, "police")
            return
        runtime.inbound_dos.record()
        apply_incoming(runtime, TurnMessage.from_dict(incoming))


def apply_incoming(runtime, message: TurnMessage) -> None:
    if runtime.reference_v3:
        refusal = refuse_turn(message.to_dict())
        if refusal:
            runtime.disputes.append(f"reference-v3 refused turn {message.step}: {refusal}")
            runtime._result = (TECHNICAL_LOSS, "police")
            notify(runtime, {"type": "protocol_error", "step": message.step, "reason": refusal})
            return
    outcome = runtime.handler.process(message)
    runtime.disputes.extend(outcome.disputes)
    if outcome.replayed:
        notify(runtime, {"type": "replay_ignored", "step": message.step})
        return
    # One Bayes-filter update happened inside `handler.process` above (diffuse
    # then observe_smell): the scent that drove it and the posterior it left
    # behind, so the report can show the calculation instead of only its
    # eventual effect on where the police walked.
    runtime.belief_log.append(
        {
            "step": message.step,
            "smell_grid": message.smell_grid,
            "belief": belief_matrix(runtime.threat, runtime.state.board.size),
        }
    )
    notify(runtime, {"type": "incoming", "step": message.step, "hint": message.hint})
    if outcome.i_won:
        runtime._result = (CAPTURE, "police")
    elif outcome.opponent_won:
        # The survival claim rides the thief's own final move, so without this
        # check the police would concede one move short of the thief's own
        # count -- step 34 in its log against the thief's 35 (Appendix He 46/47
        # rely on both sides having played the same number of rounds). Local
        # only: the thief's own loop set its result the instant it *sent* that
        # claim, without waiting for a reply (a self-verified claim needs none),
        # so a transmitted message here would sit unread in the shared
        # transport and be mistaken for the next sub-game's first turn.
        if not runtime.reference_v3 and not runtime.rules.out_of_steps(runtime.state):
            take_turn(runtime, transmit=False)
        if runtime.reference_v3:
            _drain_reference_terminal(runtime)
        runtime._result = (SURVIVAL, "thief")
    elif runtime.rules.out_of_steps(runtime.state):
        runtime._result = ceiling_result(runtime)
    else:
        take_turn(runtime)


def ceiling_result(runtime) -> tuple[str, str | None]:
    if runtime.rules.thief_survived(runtime.state.step_number):
        return (SURVIVAL, "thief")
    return (TIMEOUT, None)


def turn_timeout(runtime) -> float:
    if runtime.league:
        return float(runtime.config.get("network.watchdog_timeout_seconds") or 60.0)
    return float(
        runtime.config.get("network.turn_timeout_seconds")
        or runtime.config.get("network.watchdog_timeout_seconds")
        or 60.0
    )


def _drain_reference_terminal(runtime) -> None:
    """Consume the reference thief's post-survival terminal seal.

    Reference-v3 sends a final step after the survival claim. It is not another
    Police turn, but leaving it in the held series queue would make the next
    sub-game read stale mail as its opener. The commitment is retained for the
    mutual audit before the message is discarded from the turn queue.
    """
    drain = getattr(runtime.transport, "drain_turns", None)
    if not callable(drain):
        return
    for raw in drain(timeout=min(2.0, runtime._turn_timeout())):
        try:
            message = TurnMessage.from_dict(raw)
        except Exception:  # malformed terminal mail cannot be used as evidence
            continue
        if message.step > runtime.state.step_number:
            runtime.handler.remember_commit(message)
