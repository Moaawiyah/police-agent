"""The verbal layer: what reaches the wire after a small model has spoken.

Two things are being defended. A hint must obey the agreed word cap and carry no
grid coordinates (Appendix He 26 and 27), whatever the model returns -- and the
banter must never be able to cost a game, so every possible failure of a local
model has to come out as an ordinary line.
"""

import random

import pytest

from police_agent.strategy.talk import HintWriter


def writer(reply="Closing in on you near Times Square.", **kwargs) -> HintWriter:
    """A hint writer whose 'model' returns a fixed reply."""
    kwargs.setdefault("setting", "New York")
    kwargs.setdefault("rng", random.Random(0))
    return HintWriter(lambda prompt, system: reply, **kwargs)


def hint(subject: HintWriter, claim=None, opponent="") -> str:
    text, _intent = subject(state=None, capture_claim=claim, opponent_hint=opponent)
    return text


class TestWhatTheModelSays:
    def test_the_models_line_is_what_goes_out(self):
        assert hint(writer("Nowhere to run past Grand Central.")) == (
            "Nowhere to run past Grand Central."
        )

    def test_a_long_answer_is_cut_to_the_agreed_word_cap(self):
        subject = writer(" ".join(f"word{n}" for n in range(40)), max_words=15)

        assert len(hint(subject).split()) == 15

    def test_quotes_and_markdown_the_model_wrapped_it_in_are_stripped(self):
        assert hint(writer('"**Times Square is mine.**"')) == "Times Square is mine."

    def test_only_the_first_line_is_taken(self):
        assert hint(writer("Catch me at Harlem.\nHere is another line.")) == "Catch me at Harlem."


class TestQwenThinksOutLoud:
    def test_a_reasoning_block_never_reaches_the_wire(self):
        reply = "<think>The cop should sound confident.</think>\nI am already on Wall Street."

        assert hint(writer(reply)) == "I am already on Wall Street."

    def test_reasoning_cut_off_mid_thought_does_not_leak_either(self):
        """A thinking block that ran out of tokens has no closing tag."""
        assert hint(writer("<think>Let me consider the best taunt to")) != ""
        assert "think" not in hint(writer("<think>Let me consider the best taunt to"))


class TestNoCoordinatesReachTheWire:
    @pytest.mark.parametrize(
        "reply",
        [
            "I can see you at 3,4 by the bridge.",
            "You are in cell 12 near Soho.",
            "Heading for row 5, hold Central Park.",
            "Spotted you at (2, 6) on Broadway.",
        ],
    )
    def test_a_model_that_invents_a_grid_reference_has_it_removed(self, reply):
        result = hint(writer(reply))

        assert not any(part.strip("().,").replace(",", "").isdigit() for part in result.split())

    def test_a_landmark_that_merely_contains_a_digit_survives(self):
        """A street number is a name, not a coordinate."""
        assert "5th" in hint(writer("Meet me on 5th Avenue, thief."))


class TestBanterNeverCostsAGame:
    def test_a_model_that_raises_falls_back_to_a_line(self):
        def explode(prompt, system):
            raise ConnectionError("ollama is not running")

        subject = HintWriter(explode, "New York", rng=random.Random(0))

        assert hint(subject) != ""

    def test_a_model_that_answers_with_nothing_falls_back(self):
        assert hint(writer("   \n  ")) != ""

    def test_a_reply_that_was_nothing_but_coordinates_falls_back(self):
        assert hint(writer("3,4")) != ""

    def test_with_no_model_at_all_the_fallback_still_speaks(self):
        subject = HintWriter(None, "New York", rng=random.Random(0))

        assert hint(subject) != ""

    def test_the_fallback_also_obeys_the_word_cap(self):
        subject = HintWriter(None, "New York", max_words=4, rng=random.Random(0))

        assert len(hint(subject).split()) <= 4

    def test_the_model_only_speaks_every_nth_turn_when_asked_to(self):
        calls = []
        subject = HintWriter(lambda p, s: calls.append(1) or "Soho.", "New York", every_n_steps=3)

        for _ in range(6):
            hint(subject)

        assert len(calls) == 2


class TestIntentIsSealedBeforeTheModelSpeaks:
    """ch. 5.3.1: whether a hint is honest or a lie must be decided before it
    is written, not read off what the model happened to say."""

    def test_a_zero_bluff_rate_always_declares_the_truth(self):
        subject = writer(bluff_rate=0.0)

        for _ in range(5):
            _, intent = subject(None, None, "")
            assert intent == "truth"

    def test_a_certain_bluff_rate_always_declares_a_lie(self):
        subject = writer(bluff_rate=1.0)

        for _ in range(5):
            _, intent = subject(None, None, "")
            assert intent == "lie"

    def test_the_declared_intent_shapes_what_the_model_is_told(self):
        seen = {}
        subject = writer(bluff_rate=1.0)
        subject._ask = lambda prompt, system: seen.setdefault("system", system) or "Soho."

        subject(None, None, "")

        assert "mislead" in seen["system"].lower()

    def test_a_fallback_line_is_always_sealed_truthful(self):
        """No model, or the turn between spoken ones: no claim was made, so
        nothing to declare a lie about."""
        subject = HintWriter(None, "New York", bluff_rate=1.0, rng=random.Random(0))

        _, intent = subject(None, None, "")

        assert intent == "truth"
