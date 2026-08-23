"""The verbal layer's two askers, and the one gate and ledger they must share.

Writing a taunt and reading the thief's are two calls to one server against one
agreed rate. Resolving them into separate rate limiters would let this peer make
twice the requests it signed up for while every counter still looked correct,
which is the sort of thing only a test that counts across both can catch.
"""

import pytest

from police_agent.shared.gatekeeper import Gatekeeper, GatekeeperLockedError, GateLimits
from police_agent.shared.tokens import TokenLedger
from police_agent.strategy.bluff import resolve_bluff_analyst
from police_agent.strategy.talk import asker_from_config, resolve_hint_writer
from tests.conftest import config_with
from tests.infra.test_ollama import fake_urlopen

COUNTED = b'{"response": "Heading north past Harlem.", "prompt_eval_count": 60, "eval_count": 9}'


def talking_config(**overrides):
    return config_with(trash_talk__provider="ollama", **overrides)


class TestOneGateForBothHalves:
    def test_the_writer_and_the_analyst_spend_from_the_same_bucket(self, monkeypatch):
        fake_urlopen(monkeypatch, body=COUNTED)
        gate, ledger, config = Gatekeeper(), TokenLedger(), talking_config()

        resolve_hint_writer(config, gate=gate, ledger=ledger)(None, None)
        resolve_bluff_analyst(config, gate, ledger)._ask("what did it say", "")

        assert gate.counts["submitted"] == 2
        assert ledger.calls == 2

    def test_locking_the_gate_silences_both_of_them_at_once(self, monkeypatch):
        """One runaway loop must not leave the other half still calling out."""
        fake_urlopen(monkeypatch, body=COUNTED)
        gate, config = Gatekeeper(), talking_config()
        writer = resolve_hint_writer(config, gate=gate)
        analyst = resolve_bluff_analyst(config, gate)
        gate.dos.record(10_000)

        text, _intent = writer(None, None)
        assert text != ""  # a canned line, never an exception
        assert analyst.assess("heading north", (0, 0), None).direction is not None

    def test_the_silence_is_the_gate_refusing_and_not_the_model_answering(self, monkeypatch):
        """What the two halves swallow above is a refusal, raised where it belongs."""
        fake_urlopen(monkeypatch, body=COUNTED)
        gate = Gatekeeper()
        gate.dos.record(10_000)
        ask = asker_from_config(talking_config().get, gate)

        with pytest.raises(GatekeeperLockedError):
            ask("taunt him")


class TestTheGateIsBuiltFromTheAgreedFile:
    def test_an_asker_made_without_one_still_reads_the_agreed_limits(self, monkeypatch):
        """A standalone asker is gated too, on the terms both peers signed."""
        captured = {}

        def spy(*_args, gate=None, **_kwargs):
            captured["limits"] = gate.limits
            return lambda prompt, system="": ""

        monkeypatch.setattr("police_agent.strategy.talk_asker.ollama_asker", spy)

        asker_from_config(talking_config(gatekeeper__requests_per_minute=90).get)

        assert captured["limits"].requests_per_minute == 90

    def test_the_taunts_whole_allowance_defaults_to_its_socket_timeout(self, monkeypatch):
        """A turn is not a budget to spend retrying: see `shared/gatekeeper.py`."""
        fake_urlopen(monkeypatch, body=COUNTED)
        gate = Gatekeeper(GateLimits(retry_backoff_seconds=99.0))
        config = talking_config(trash_talk__timeout_seconds=0.5)

        asker_from_config(config.get, gate)("taunt him")

        assert gate.counts["retried"] == 0
