"""The token ledger: what a sub-game spent, per step and in total.

Appendix He 54 makes the figure mandatory, so the thing worth pinning is that it
is arithmetic on numbers a provider handed us -- never a guess, and never reset
by accident when a turn boundary passes.
"""

from police_agent.shared.tokens import TokenLedger, Usage


def ledger(*calls: tuple[int, int]) -> TokenLedger:
    subject = TokenLedger()
    for prompt, completion in calls:
        subject.record(Usage(prompt, completion))
    return subject


class TestOneCallsCost:
    def test_a_usage_totals_both_halves(self):
        assert Usage(120, 30).total == 150

    def test_an_unreported_call_costs_nothing_rather_than_something_invented(self):
        assert Usage().total == 0


class TestTheSubGameTally:
    def test_a_fresh_ledger_has_spent_nothing(self):
        assert ledger().snapshot() == {
            "tokens_step": 0,
            "tokens_total": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model_calls": 0,
        }

    def test_calls_accumulate_across_the_sub_game(self):
        subject = ledger((100, 20), (80, 15))

        assert subject.total == 215
        assert subject.prompt_tokens == 180
        assert subject.completion_tokens == 35

    def test_the_two_halves_are_kept_apart_for_a_metered_provider(self):
        """They are priced differently, so a folded-together figure cannot be checked."""
        snapshot = ledger((100, 20)).snapshot()

        assert (snapshot["prompt_tokens"], snapshot["completion_tokens"]) == (100, 20)

    def test_a_free_local_model_still_counts_as_a_call(self):
        """Zero tokens is not the same as never having asked -- Appendix Vav 21."""
        subject = ledger((0, 0), (0, 0))

        assert (subject.total, subject.calls) == (0, 2)


class TestTheStepBoundary:
    def test_a_new_step_zeroes_this_turns_spend_and_not_the_match_total(self):
        subject = ledger((100, 20))

        subject.begin_step()

        assert subject.snapshot()["tokens_step"] == 0
        assert subject.snapshot()["tokens_total"] == 120

    def test_what_a_step_spent_is_what_it_reports(self):
        subject = ledger((100, 20))
        subject.begin_step()
        subject.record(Usage(7, 3))

        assert subject.snapshot()["tokens_step"] == 10

    def test_several_calls_in_one_turn_all_land_on_that_turn(self):
        """Writing a taunt and reading the thief's are two calls on one step."""
        subject = TokenLedger()
        subject.begin_step()
        subject.record(Usage(40, 10))
        subject.record(Usage(30, 5))

        assert subject.snapshot()["tokens_step"] == 85
