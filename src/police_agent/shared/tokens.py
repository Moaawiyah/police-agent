"""Counting the language-model tokens a sub-game actually consumed.

Appendix He 54 makes the figure mandatory in the end-of-game JSON: the tokens
spent in this sub-game, and in the series. Appendix Vav table 18 sets the series
estimate at ~200000, and table 21 records that a local Ollama model costs zero
*API* tokens -- so on the shipped configuration this number is real work measured
honestly and no money, which is not the same thing as nothing to report.

Every count here comes from the provider's own reply (`prompt_eval_count` and
`eval_count` for Ollama). Nothing is estimated from character counts: a report
that guesses is worse than one that says zero, because zero is checkable.

A ledger measures; it does not enforce. Nothing in this file refuses a call for
being expensive -- rationing outbound work is the Gatekeeper's job, and the two
kinds of "token" must not be confused (spec ch. 9.3.1).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    """What one model call cost, as the provider reported it.

    Both halves are kept rather than only the sum, because a metered provider
    prices them differently and a report that folded them together could not be
    reconciled against an invoice.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        """This call's combined prompt + completion tokens."""
        return self.prompt_tokens + self.completion_tokens


class TokenLedger:
    """A running tally for one sub-game, kept on the runtime beside its records.

    `begin_step` is what makes "tokens this step" meaningful: the runtime marks
    each turn as it starts, so the figure in a live status line is this turn's
    spend rather than a number that only ever grows.
    """

    def __init__(self) -> None:
        """An empty tally, ready to record calls as they happen."""
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.step_tokens = 0
        self.step_prompt_tokens = 0
        self.step_completion_tokens = 0

    @property
    def total(self) -> int:
        """This sub-game's combined prompt + completion tokens so far."""
        return self.prompt_tokens + self.completion_tokens

    def begin_step(self) -> None:
        """Start a new turn's accounting, leaving the sub-game total alone."""
        self.step_tokens = 0
        self.step_prompt_tokens = 0
        self.step_completion_tokens = 0

    def record(self, usage: Usage) -> None:
        """Add one call's reported consumption.

        Called even for a free local model, whose usage is genuinely zero: a call
        that happened is still a call, and `calls` is what distinguishes "the
        model was never asked" from "the model answered without charging".
        """
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.step_tokens += usage.total
        self.step_prompt_tokens += usage.prompt_tokens
        self.step_completion_tokens += usage.completion_tokens

    def snapshot(self) -> dict:
        """The block the end-of-game JSON carries (Appendix He 54)."""
        return {
            "tokens_step": self.step_tokens,
            "tokens_total": self.total,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "model_calls": self.calls,
        }

    def step_snapshot(self) -> dict:
        """This step's own input/output split and the running total through
        it -- what the sealed per-step record carries, matching the sibling
        thief repo's own richer per-step schema (`tokens_input`/`tokens_output`/
        `tokens_step`/`tokens_total`) rather than only a single flat figure."""
        return {
            "tokens_input": self.step_prompt_tokens,
            "tokens_output": self.step_completion_tokens,
            "tokens_step": self.step_tokens,
            "tokens_total": self.total,
        }
