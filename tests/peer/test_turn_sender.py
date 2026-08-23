"""take_turn's own bookkeeping: sealing tokens, and keeping belief honest."""

from types import SimpleNamespace

from police_agent.constants import Direction
from police_agent.domain.actions import barrier, move
from police_agent.domain.own_state import OwnGameState
from police_agent.peer.turn_sender import take_turn
from police_agent.shared.tokens import TokenLedger, Usage
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.decision import Decision


def _runtime(threat, decision, usage=None):
    tokens = TokenLedger()

    def decide(state, threat, barriers_max):
        if usage is not None:
            tokens.record(usage)
        return decision

    return SimpleNamespace(
        state=OwnGameState((3, 3), 7),
        threat=threat,
        barriers_max=5,
        tokens=tokens,
        records=[],
        brain=SimpleNamespace(decide=decide),
    )


class TestBeliefStaysHonestAboutBarriers:
    def test_a_wall_the_police_just_built_is_excluded_from_belief(self):
        """Without the fix, a fresh scent reading on the walled cell survives
        take_turn untouched -- the model would keep believing the thief could
        be standing inside a wall this same peer just built."""
        threat = BeliefGrid(7)
        threat.observe_smell({"3,3": 0.9})
        assert threat.top_cells(1)[0] == ((3, 3), threat.top_cells(1)[0][1])
        assert threat.top_cells(1)[0][1] > 0.05  # real, non-trivial mass before the wall

        runtime = _runtime(threat, Decision(barrier(), "test wall underfoot"))
        take_turn(runtime, transmit=False)

        row, col = 3, 3
        assert threat.as_matrix()[row][col] < 1e-9

    def test_a_move_leaves_belief_untouched(self):
        """No barrier this turn -- nothing for the fix to exclude."""
        threat = BeliefGrid(7)
        threat.observe_smell({"3,3": 0.9})
        before = threat.as_matrix()

        runtime = _runtime(threat, Decision(move(Direction.N), "test step"))
        take_turn(runtime, transmit=False)

        assert threat.as_matrix() == before


def _full_runtime(threat, decision, usage):
    """A runtime that actually reaches `hint_writer` (`transmit=True` path),
    with the writer recording tokens the way `infra/ollama.py::ollama_asker`
    really does -- mirroring where a turn's only LLM call actually happens."""
    tokens = TokenLedger()

    def hint_writer(state, claim, opponent_hint):
        tokens.record(usage)
        return "a hint", "truth"

    return SimpleNamespace(
        state=OwnGameState((3, 3), 7),
        threat=threat,
        barriers_max=5,
        tokens=tokens,
        records=[],
        brain=SimpleNamespace(decide=lambda state, threat, barriers_max: decision),
        hint_writer=hint_writer,
        scent=SimpleNamespace(emit=lambda pos: {}),
        transport=SimpleNamespace(send_turn=lambda msg: None),
        handler=SimpleNamespace(history=[]),
        notify=lambda event: None,
    )


class TestTokenAccounting:
    def test_the_sealed_record_carries_this_step_s_tokens(self):
        threat = BeliefGrid(7)
        runtime = _runtime(
            threat,
            Decision(barrier(), "test wall"),
            usage=Usage(prompt_tokens=10, completion_tokens=32),
        )

        take_turn(runtime, transmit=False)

        assert runtime.records[-1]["payload"]["tokens"] == 42

    def test_the_sealed_tokens_reflect_the_hint_writer_s_own_spend(self):
        """Regression: the shipped brain never calls an LLM -- only the hint
        writer does, and sealing used to happen before that call ran, so
        every step's declared spend was always the zero `begin_step()` just
        set, however much the hint actually cost."""
        threat = BeliefGrid(7)
        runtime = _full_runtime(threat, Decision(move(Direction.N), "test step"), Usage(10, 32))

        take_turn(runtime)

        payload = runtime.records[-1]["payload"]
        assert payload["tokens"] == 42
        assert (payload["tokens_input"], payload["tokens_output"]) == (10, 32)
        assert (payload["tokens_step"], payload["tokens_total"]) == (42, 42)

    def test_a_message_nobody_will_hear_spends_no_tokens_writing_it(self):
        """`transmit=False` means the opponent already concluded its game and
        is not listening -- writing a hint for it would be a wasted call."""
        threat = BeliefGrid(7)
        runtime = _full_runtime(threat, Decision(move(Direction.N), "test step"), Usage(10, 32))

        take_turn(runtime, transmit=False)

        assert runtime.records[-1]["payload"]["tokens"] == 0
