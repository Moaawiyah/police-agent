"""What the model is told, and which model gets told it.

The prompt is where the specification's hard line sits. Appendix He 27 forbids
numeric locations on the wire, and the way this agent guarantees it is not by
filtering the answer but by never putting a cell in the question -- so that is
what is asserted here.
"""

import json
from contextlib import contextmanager

from police_agent.infra.ollama import DEFAULT_MODEL
from police_agent.strategy.talk import HintWriter, resolve_hint_writer
from tests.conftest import config_with


def recorder(reply: str = "Times Square is mine."):
    """A stand-in model that keeps whatever it was asked."""
    seen: dict = {}

    def ask(prompt, system):
        seen["prompt"], seen["system"] = prompt, system
        return reply

    return seen, ask


class TestWhatTheModelIsTold:
    def test_it_is_never_told_where_the_police_is(self):
        seen, ask = recorder()

        HintWriter(ask, "New York")(state=None, capture_claim=(3, 4), opponent_hint="hi")

        assert "3" not in seen["prompt"]
        assert "4" not in seen["prompt"]

    def test_the_thiefs_last_line_is_put_to_it_to_answer(self):
        seen, ask = recorder()

        HintWriter(ask, "New York")(None, None, "You will never find me.")

        assert "You will never find me." in seen["prompt"]

    def test_silence_from_the_thief_is_said_plainly_rather_than_faked(self):
        seen, ask = recorder()

        HintWriter(ask, "New York")(None, None, "")

        assert "nothing" in seen["prompt"].lower()

    def test_the_agreed_word_cap_and_city_are_both_pinned_in_the_system_prompt(self):
        seen, ask = recorder()

        HintWriter(ask, "New York", max_words=15)(None, None, "")

        assert "15 words" in seen["system"]
        assert "New York" in seen["system"]

    def test_it_is_told_not_to_write_coordinates(self):
        seen, ask = recorder()

        HintWriter(ask, "New York")(None, None, "")

        assert "coordinates" in seen["system"].lower()

    def test_closing_in_reads_differently_from_still_searching(self):
        seen, ask = recorder()
        subject = HintWriter(ask, "New York")

        subject(None, (1, 1), "")
        closing = seen["prompt"]
        subject(None, None, "")

        assert closing != seen["prompt"]

    def test_an_unnamed_city_still_produces_a_usable_prompt(self):
        seen, ask = recorder()

        HintWriter(ask, "")(None, None, "")

        assert "unnamed city" in seen["system"]


class TestWhichModelGetsAsked:
    def test_the_shipped_default_asks_the_local_model(self):
        assert resolve_hint_writer(None)._ask is not None
        assert resolve_hint_writer(config_with(trash_talk__provider="ollama"))._ask is not None

    def test_a_blank_choice_means_the_default_not_a_provider_named_none(self):
        assert resolve_hint_writer(config_with(trash_talk__provider=None))._ask is not None

    def test_the_template_provider_asks_nobody(self):
        assert resolve_hint_writer(config_with(trash_talk__provider="template"))._ask is None

    def test_an_unrecognised_provider_costs_banter_and_not_the_match(self):
        assert resolve_hint_writer(config_with(trash_talk__provider="gpt9"))._ask is None

    def test_the_signed_word_cap_comes_from_the_agreed_terms(self):
        assert resolve_hint_writer(config_with())._max_words == 15

    def test_it_survives_having_no_config_at_all(self):
        assert resolve_hint_writer(None)._max_words == 15


class TestTheResolvedWriterReallyCallsOllama:
    def test_a_hint_makes_it_all_the_way_out_to_the_server_and_back(self, monkeypatch):
        sent: dict = {}

        @contextmanager
        def urlopen(request, timeout=None):
            sent["payload"] = json.loads(request.data)
            sent["timeout"] = timeout

            class Fake:
                def read(self):
                    return b'{"response": "I own every bridge off this island."}'

            yield Fake()

        monkeypatch.setattr("urllib.request.urlopen", urlopen)
        writer = resolve_hint_writer(
            config_with(trash_talk__provider="ollama", trash_talk__timeout_seconds=1.5)
        )

        text, _intent = writer(None, None, "catch me")
        assert text == "I own every bridge off this island."
        assert sent["payload"]["model"] == DEFAULT_MODEL
        assert sent["timeout"] == 1.5

    def test_a_private_config_can_name_a_different_model(self, monkeypatch):
        sent: dict = {}

        @contextmanager
        def urlopen(request, timeout=None):
            sent["payload"] = json.loads(request.data)

            class Fake:
                def read(self):
                    return b'{"response": "Soho is mine."}'

            yield Fake()

        monkeypatch.setattr("urllib.request.urlopen", urlopen)
        writer = resolve_hint_writer(
            config_with(trash_talk__provider="ollama", trash_talk__model="llama3.2")
        )
        writer(None, None, "")

        assert sent["payload"]["model"] == "llama3.2"
