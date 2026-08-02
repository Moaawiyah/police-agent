"""Turning a sentence the thief wrote into a direction, or into nothing.

Nothing is a perfectly good answer here and the tests lean on it: inventing a
claim the thief never made would feed the belief map evidence that does not
exist, which is worse than reading no hints at all.
"""

import pytest

from police_agent.constants import Direction
from police_agent.strategy.hint_claim import claimed_direction


def model(reply: str):
    """A stand-in classifier that always answers the same way."""
    return lambda prompt, system: reply


class TestReadingWithAModel:
    @pytest.mark.parametrize(
        "reply, expected",
        [
            ("N", Direction.N),
            ("S", Direction.S),
            ("E", Direction.E),
            ("W", Direction.W),
        ],
    )
    def test_a_one_letter_answer_is_taken_at_face_value(self, reply, expected):
        assert claimed_direction("slipping through the streets", model(reply)) is expected

    def test_a_chattier_model_is_still_understood(self):
        """Small models add padding however plainly they are told not to."""
        assert claimed_direction("heading out", model("The answer is: N.")) is Direction.N

    def test_the_model_beats_the_keywords_when_it_has_an_opinion(self):
        """It reads intent; keywords only read words."""
        assert claimed_direction("making for the uptown lights", model("S")) is Direction.S


class TestFallingBackToKeywords:
    def test_a_model_that_finds_no_claim_leaves_the_keywords_to_try(self):
        assert claimed_direction("I went north, officer", model("-")) is Direction.N

    def test_a_model_that_raises_leaves_the_keywords_to_try(self):
        def explode(prompt, system):
            raise ConnectionError("ollama is not running")

        assert claimed_direction("I went north, officer", explode) is Direction.N

    def test_with_no_model_at_all_the_keywords_are_the_whole_reader(self):
        assert claimed_direction("heading south past the market") is Direction.S

    @pytest.mark.parametrize(
        "hint, expected",
        [
            ("running north", Direction.N),
            ("gone southward", Direction.S),
            ("eastern edge of town", Direction.E),
            ("slipped west", Direction.W),
            ("heading uptown", Direction.N),
            ("down in the downtown crowds", Direction.S),
        ],
    )
    def test_the_words_it_knows(self, hint, expected):
        assert claimed_direction(hint) is expected


class TestClaimingNothing:
    def test_an_empty_hint_claims_nothing(self):
        assert claimed_direction("") is None
        assert claimed_direction("   ") is None
        assert claimed_direction(None) is None

    def test_a_hint_with_no_direction_in_it_claims_nothing(self):
        assert claimed_direction("catch me if you can, officer") is None

    def test_two_directions_at_once_claim_nothing(self):
        """ "North of the bridge, west of the park" is not a bearing."""
        assert claimed_direction("north of the bridge, west of the park") is None

    def test_a_direction_buried_inside_another_word_is_not_a_claim(self):
        assert claimed_direction("I am in Northampton") is None

    def test_a_model_answering_with_noise_falls_through_to_no_claim(self):
        assert claimed_direction("catch me if you can", model("???")) is None
