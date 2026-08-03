"""What a model call cost, and the gate it had to leave by.

Two things are being defended. The reported consumption has to be the server's
own count and nothing else (Appendix He 54), and the asker the strategy layer
holds has to stay an ordinary `ask(prompt, system) -> str` -- the seam that lets
`tests/strategy/test_talk.py` inject a two-argument function is worth more than
any convenience a richer return type would buy.
"""

import pytest

from police_agent.infra.ollama import ask_ollama, ask_ollama_usage, ollama_asker
from police_agent.shared.gatekeeper import Gatekeeper, GatekeeperLockedError, GateLimits
from police_agent.shared.tokens import TokenLedger
from tests.infra.test_ollama import fake_urlopen

COUNTED = b'{"response": "Times Square is mine.", "prompt_eval_count": 120, "eval_count": 18}'


class TestTheServersOwnCounts:
    def test_the_reply_carries_the_counts_the_server_reported(self, monkeypatch):
        fake_urlopen(monkeypatch, body=COUNTED)

        text, usage = ask_ollama_usage("taunt him")

        assert text == "Times Square is mine."
        assert (usage.prompt_tokens, usage.completion_tokens) == (120, 18)

    def test_an_older_server_that_reports_nothing_costs_zero_not_a_guess(self, monkeypatch):
        """A number nobody can check is worse than an honest zero."""
        fake_urlopen(monkeypatch)

        _, usage = ask_ollama_usage("taunt him")

        assert usage.total == 0

    def test_the_plain_text_call_still_returns_only_text(self, monkeypatch):
        """The existing callers ask for a line, and still get exactly that."""
        fake_urlopen(monkeypatch, body=COUNTED)

        assert ask_ollama("taunt him") == "Times Square is mine."


class TestTheAskerTheStrategyLayerHolds:
    def test_it_is_still_a_two_argument_function_returning_a_string(self, monkeypatch):
        fake_urlopen(monkeypatch, body=COUNTED)

        ask = ollama_asker()

        assert ask("taunt him", "you are a detective") == "Times Square is mine."

    def test_what_it_spends_lands_in_the_ledger_it_was_given(self, monkeypatch):
        fake_urlopen(monkeypatch, body=COUNTED)
        ledger = TokenLedger()

        ollama_asker(ledger=ledger)("taunt him")

        assert (ledger.total, ledger.calls) == (138, 1)

    def test_an_asker_with_no_ledger_works_and_simply_counts_nothing(self, monkeypatch):
        """The seam must not require the accounting to be wired up."""
        fake_urlopen(monkeypatch, body=COUNTED)

        assert ollama_asker()("taunt him") == "Times Square is mine."

    def test_a_failed_call_adds_nothing_to_the_tally(self, monkeypatch):
        def urlopen(request, timeout=None):
            raise ConnectionError("ollama is not running")

        monkeypatch.setattr("urllib.request.urlopen", urlopen)
        ledger = TokenLedger()
        ask = ollama_asker(ledger=ledger, gate=Gatekeeper(GateLimits(max_retries=0)))

        with pytest.raises(Exception, match="failed"):
            ask("taunt him")

        assert (ledger.total, ledger.calls) == (0, 0)


class TestNothingReachesTheModelPastTheGate:
    def test_every_call_is_submitted_to_the_gatekeeper(self, monkeypatch):
        fake_urlopen(monkeypatch, body=COUNTED)
        gate = Gatekeeper()

        ollama_asker(gate=gate)("taunt him")

        assert gate.counts["submitted"] == 1
        assert gate.counts["sent"] == 1

    def test_a_locked_gate_stops_the_call_before_the_socket(self, monkeypatch):
        """Which the hint writer turns into a canned line, not a lost game."""
        sent = fake_urlopen(monkeypatch, body=COUNTED)
        gate = Gatekeeper()
        gate.dos.record(10_000)

        with pytest.raises(GatekeeperLockedError):
            ollama_asker(gate=gate)("taunt him")

        assert sent == {}

    def test_an_asker_built_without_a_gate_still_has_one(self, monkeypatch):
        """There is no ungated way through this door -- see ch. 11."""
        fake_urlopen(monkeypatch, body=COUNTED)

        ask = ollama_asker()

        assert ask.__closure__ is not None  # the gate is captured, not optional
        assert ask("taunt him") == "Times Square is mine."
