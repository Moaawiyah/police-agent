"""Replay verification labels for own and opponent production records."""

from police_agent.domain.crypto import CommitReveal
from police_agent.gui.replay import ReplayApp
from tests.conftest import config_with
from tests.gui.fake_window import FakeWindow


def sealed(step: int) -> dict:
    payload = {"step": step, "position": [step, 0], "rationale": f"step {step}"}
    return {"payload": payload, **CommitReveal.seal(payload)}


def log_of(steps: int) -> dict:
    return {
        "role": "police",
        "result": "capture",
        "winner": "police",
        "audit": {"passed": True, "verified_steps": steps},
        "records": [sealed(step) for step in range(1, steps + 1)],
        "my_log": [
            {"step": step, "position": [step, 0], "barrier": None} for step in range(1, steps + 1)
        ],
    }


def player(log: dict, opponent=None) -> tuple[ReplayApp, FakeWindow]:
    window = FakeWindow()
    return ReplayApp(config_with(), log, opponent_log=opponent, window=window), window


def test_each_step_re_verifies_its_own_commit():
    app, window = player(log_of(2))

    app.advance()

    assert "verified OK" in window.labels["commit"]
    assert window.labels["verdict"] == "step 1 (revealed)"


def test_a_rewritten_log_is_caught_as_it_is_drawn():
    log = log_of(2)
    log["records"][0]["payload"]["position"] = [6, 6]
    app, window = player(log)

    app.advance()

    assert "TAMPERED" in window.labels["commit"]
    assert "Verification FAILED" in window.labels["status"]


def test_failed_audit_is_never_labelled_verified():
    app, window = player({**log_of(1), "audit": {"passed": False}})

    app.advance()

    assert window.labels["status"].startswith("step 1/1 | Verification FAILED")


def test_a_tampered_opponent_log_fails_cross_log_verification():
    their_record = sealed(1)
    their_record["payload"]["position"] = [6, 6]
    theirs = {
        "records": [their_record],
        "my_log": [{"position": [6, 6]}],
        "audit": {"passed": True},
    }
    app, window = player(log_of(1), opponent=theirs)

    app.advance()

    assert "Verification FAILED" in window.labels["status"]
