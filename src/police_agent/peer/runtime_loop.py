"""Turn-loop operations delegated by :class:`PoliceRuntime`."""

from police_agent.domain.rules import ABORTED, CAPTURE, SURVIVAL, TECHNICAL_LOSS, TIMEOUT
from police_agent.peer.protocol import TurnMessage
from police_agent.peer.turn_sender import take_turn
from police_agent.peer.view import snapshot


def notify(runtime, event: dict) -> None:
    if runtime._listener is not None:
        runtime._listener({**event, "view": snapshot(runtime)})


def turn_loop(runtime) -> None:
    timeout = runtime._turn_timeout()
    while runtime._result is None:
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
    outcome = runtime.handler.process(message)
    runtime.disputes.extend(outcome.disputes)
    if outcome.replayed:
        notify(runtime, {"type": "replay_ignored", "step": message.step})
        return
    notify(runtime, {"type": "incoming", "step": message.step, "hint": message.hint})
    if outcome.i_won:
        runtime._result = (CAPTURE, "police")
    elif outcome.opponent_won:
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
