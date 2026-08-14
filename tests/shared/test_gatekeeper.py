"""The agreed limits, and the token bucket that gets a call through.

The retry policy has its own file next door; `gate` and `explode` below are
the fixtures both use. The DOS lock and what the report can see live in
`test_gatekeeper_dos.py`, split out to keep both files under the project's
line budget.

The sleep is injected; the clock is not. A five-second backoff taken three times
is the shipped configuration and a suite that served it would take longer than
the match it protects -- but the waiting line blocks on a condition variable,
which follows the real clock however the gate is told to measure deadlines, so
a faked clock here would simply hang.
"""

import time

import pytest

from police_agent.shared.gatekeeper import Gatekeeper, GatekeeperOverloadError, GateLimits
from tests.conftest import config_with


def gate(**limits) -> tuple[Gatekeeper, list]:
    """A gate whose backoffs are recorded rather than served."""
    slept: list[float] = []
    return Gatekeeper(GateLimits(**limits), sleep=slept.append), slept


def explode(message="the server hung up"):
    """A call that always fails, so the retry policy is what is on trial."""

    def call():
        raise ConnectionError(message)

    return call


class TestTheAgreedLimitsAreWhatItUses:
    def test_an_agreed_file_that_names_nothing_still_gets_the_appendix_values(self):
        """Status "minimum": the example value is the default the code must use."""
        assert Gatekeeper.from_config(None).limits == GateLimits(30, 2, 5.0, 3, 100)

    def test_the_shipped_agreed_file_is_what_the_gate_is_built_from(self, config):
        limits = Gatekeeper.from_config(config).limits

        assert limits.requests_per_minute == 30
        assert limits.concurrent_requests == 2
        assert limits.retry_backoff_seconds == 5.0
        assert limits.max_retries == 3
        assert limits.queue_depth == 100

    def test_a_stricter_agreement_between_the_teams_is_honoured(self):
        """The two sides may negotiate these upwards; the code must follow."""
        stricter = config_with(gatekeeper__requests_per_minute=90, gatekeeper__max_retries=5)

        limits = Gatekeeper.from_config(stricter).limits

        assert (limits.requests_per_minute, limits.max_retries) == (90, 5)

    def test_a_key_present_but_empty_lands_on_the_example_rather_than_zero(self):
        """A null in the agreed file means "not chosen", not "no rate limit"."""
        assert GateLimits.from_getter(lambda _key, default=None: None) == GateLimits()


class TestTheCallGetsThrough:
    def test_an_ordinary_call_returns_its_own_result(self):
        subject, _ = gate()

        assert subject.submit(lambda: "sent") == "sent"
        assert subject.counts["sent"] == 1

    def test_a_caller_out_of_tokens_waits_for_one_instead_of_being_dropped(self):
        """120 a minute is a token every half second, and the queue serves it.

        The point of the assertion is the pause: the call that ran out of tokens
        still returns its own result, having waited, rather than being refused.
        """
        subject, _ = gate(requests_per_minute=120)
        for _ in range(120):
            subject.submit(lambda: None)

        started = time.monotonic()
        assert subject.submit(lambda: "late but sent") == "late but sent"
        assert time.monotonic() - started >= 0.4

    def test_a_caller_whose_budget_cannot_cover_the_wait_is_told_so_at_once(self):
        subject, _ = gate(requests_per_minute=60)
        for _ in range(60):
            subject.submit(lambda: None)

        with pytest.raises(GatekeeperOverloadError, match="budget"):
            subject.submit(lambda: None, budget=0.05)

        assert subject.counts["rejected"] == 1
