"""Retrying: bounded by the agreed ceiling above, by the caller's clock below.

Split from `test_gatekeeper.py` to keep both files inside the 150-line rule, and
because these are one argument on their own. `max_retries` is a minimum the two
teams may raise but never lower, which says what may be *configured*; what it
does not say is that a caller holding a turn open must sit through all of them.
Both halves of that are pinned here.

Unlike its neighbour this file fakes the clock as well as the sleep, and can:
one submit against a full bucket never reaches the part of the waiting line that
blocks on real time. Backoff budgets are otherwise untestable without spending
the fifteen seconds the shipped configuration would take.
"""

import pytest

from police_agent.shared.gatekeeper import Gatekeeper, GateLimits
from tests.shared.test_gatekeeper import explode
from tests.shared.test_rate_limit import FakeClock


def gate(**limits) -> tuple[Gatekeeper, list]:
    """A gate whose backoffs are recorded, and whose clock they still advance."""
    clock = FakeClock()
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        clock.advance(seconds)

    return Gatekeeper(GateLimits(**limits), sleep=sleep, clock=clock), slept


class TestTheAgreedCeilingIsRespected:
    def test_a_failing_call_is_retried_up_to_the_agreed_ceiling(self):
        subject, slept = gate(max_retries=3, retry_backoff_seconds=5.0)
        attempts = []

        with pytest.raises(ConnectionError):
            subject.submit(lambda: attempts.append(1) or explode()())

        assert len(attempts) == 4  # the first try plus three retries
        assert slept == [5.0, 5.0, 5.0]
        assert subject.counts["retried"] == 3

    def test_it_never_tries_more_often_than_it_was_told_to(self):
        subject, _ = gate(max_retries=1)
        attempts = []

        with pytest.raises(ConnectionError):
            subject.submit(lambda: attempts.append(1) or explode()())

        assert len(attempts) == 2

    def test_zero_retries_is_still_one_honest_attempt(self):
        subject, _ = gate(max_retries=0)
        attempts = []

        with pytest.raises(ConnectionError):
            subject.submit(lambda: attempts.append(1) or explode()())

        assert len(attempts) == 1

    def test_the_original_failure_is_what_reaches_the_caller(self):
        """`strategy/talk.py` catches by kind, so the gate must not repackage it."""
        subject, _ = gate(max_retries=1)

        with pytest.raises(ConnectionError, match="the server hung up"):
            subject.submit(explode())

    def test_a_call_that_succeeds_on_the_second_try_costs_one_backoff(self):
        subject, slept = gate(max_retries=3)
        tries = []

        def flaky():
            tries.append(1)
            if len(tries) == 1:
                raise TimeoutError("first attempt lost")
            return "recovered"

        assert subject.submit(flaky) == "recovered"
        assert slept == [5.0]


class TestTheCallersDeadlineStopsItSooner:
    def test_a_caller_with_a_budget_stops_retrying_rather_than_overrunning_it(self):
        """A taunt shares its turn with the opponent's watchdog: better none."""
        subject, slept = gate(max_retries=3, retry_backoff_seconds=5.0)

        with pytest.raises(ConnectionError):
            subject.submit(explode(), budget=4.0)

        assert slept == []
        assert subject.counts["retried"] == 0

    def test_a_budget_that_covers_one_backoff_buys_exactly_one_retry(self):
        subject, slept = gate(max_retries=3, retry_backoff_seconds=1.0)

        with pytest.raises(ConnectionError):
            subject.submit(explode(), budget=1.5)

        assert slept == [1.0]

    def test_giving_up_early_still_raises_what_the_call_raised(self):
        """The caller must not have to tell a gate refusal from a server failure."""
        subject, _ = gate(max_retries=3, retry_backoff_seconds=5.0)

        with pytest.raises(ConnectionError, match="the server hung up"):
            subject.submit(explode(), budget=0.5)
