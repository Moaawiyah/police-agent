"""Building a fake police log and an off-screen `ReplayApp` for it.

Split out of test_replay.py so every replay test file can share the one
builder, following the same pattern `tests/infra/fake_ngrok.py` uses.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.gui.replay import ReplayApp
from tests.conftest import config_with
from tests.gui.fake_window import FakeWindow


def sealed(step: int) -> dict:
    payload = {"step": step, "position": [step, 0], "rationale": f"step {step}"}
    return {"payload": payload, **CommitReveal.seal(payload)}


def log_of(steps: int, smell: dict | None = None) -> dict:
    """A police log of `steps` moves south from the corner, with the thief heard."""
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "audit": {"passed": True, "verified_steps": steps},
        "opponent_reliability": 0.5,
        "records": [sealed(step) for step in range(1, steps + 1)],
        "history": [
            {"step": step, "hint": f"hint {step}", "smell_grid": smell or {}}
            for step in range(1, steps + 1)
        ],
        "my_log": [
            {"step": step, "position": [step, 0], "barrier": None} for step in range(1, steps + 1)
        ],
    }


def player(log: dict, opponent=None) -> tuple[ReplayApp, FakeWindow]:
    window = FakeWindow()
    return ReplayApp(config_with(), log, opponent_log=opponent, window=window), window
