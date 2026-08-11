"""Playing one turn: decide, apply, seal, send.

Split out of `runtime.py` so both files stay within the 150-line rule, and
because the ordering here is the part worth reading on its own. It is fixed:
the move is applied to local state *before* it is sealed, and sealed before it
is sent. A message that went out before the state was committed to would be a
promise this peer had not yet made to itself.

Takes the runtime rather than a dozen arguments. That is a deliberate trade: the
alternative threads state, brain, threat, rules, transport, records and config
through every call, and the coupling is real either way.
"""

from police_agent.constants import Cell, MoveType
from police_agent.domain.actions import hold
from police_agent.peer.sealing import build_turn_message, sealed_step_record


def take_turn(runtime, claim_response: dict | None = None, transmit: bool = True) -> None:
    """Compute this peer's turn, commit to it locally, and (usually) hand it
    to the opponent.

    `transmit=False` is for the one case where sending would actively hurt:
    the opponent has already locally concluded its own game (a self-verified
    survival claim needs no reply, so it never waits for one) and is not
    listening. A message nobody reads would sit in the shared transport's
    queue and, once the series moves on, be mistaken for the next sub-game's
    first turn -- the transport is held open across the whole series, not
    rebuilt per sub-game. The move still gets applied and sealed locally, so
    this peer's own step count and log stay in step with the opponent's.
    """
    # Opens this step's token accounting (Appendix He 54). Marked before the
    # brain runs rather than after the hint is written, so anything the turn
    # spends on a model is attributed to the turn that spent it.
    runtime.tokens.begin_step()
    decision = runtime.brain.decide(runtime.state, runtime.threat, runtime.barriers_max)
    if not runtime.state.apply_move(decision.action, runtime.barriers_max):
        # The brain is contractually forbidden from returning an illegal action,
        # so reaching this is a bug in the strategy, not a game event. Holding
        # keeps the match alive and lets the audit show what happened, rather
        # than crashing this peer into a technical loss over someone else's bug.
        runtime.state.apply_move(hold(), runtime.barriers_max)
        decision = _held_instead(decision)

    claim = _capture_claim(runtime, decision)
    record = sealed_step_record(
        runtime.state, decision.rationale, claim, runtime.tokens.step_tokens
    )
    runtime.records.append(record)
    if not transmit:
        return
    message = build_turn_message(
        runtime.state,
        commit=record["commit"],
        smell_grid=runtime.scent.emit(runtime.state.position),
        hint=runtime.hint_writer(runtime.state, claim, _opponent_hint(runtime)),
        capture_claim=claim,
        claim_response=claim_response,
    )
    runtime.transport.send_turn(message.to_dict())
    runtime.notify(
        {
            "type": "moved",
            "decision": decision,
            "commit": record["commit"],
            # The line that went out with the move. It is nowhere in the sealed
            # record -- the payload is the peer's *truth*, and a taunt is not --
            # so an observer that missed this event cannot recover it later.
            "hint": message.hint,
        }
    )


def _opponent_hint(runtime) -> str:
    """The last thing the thief said, so this turn's line can answer it.

    Free text from another team's process, passed to the verbal layer and
    nowhere near a decision -- the specification permits it to be a lie
    (ch. 4.4), so believing any of it would be the point of the trap.
    """
    history = runtime.handler.history
    return str(history[-1].get("hint", "")) if history else ""


def _capture_claim(runtime, decision) -> Cell | None:
    """The cell the police claims the thief occupies: the one it just stepped onto.

    Only a step is a claim. Placing a barrier or holding does not move the
    police, so re-claiming the same cell would ask the thief a question it has
    already answered and burn a turn doing it.
    """
    if decision.action.move_type is not MoveType.MOVE:
        return None
    return runtime.state.position


def _held_instead(decision):
    """Rewrite a rejected decision as the HOLD that was actually applied.

    The sealed record must describe what happened, not what was intended; an
    audit compares the record against the revealed moves, and a record claiming
    a move that never landed would fail against this peer's own honest log.
    """
    from police_agent.strategy.decision import Decision

    return Decision(hold(), f"held: strategy returned an illegal action ({decision.action})")
