"""The waiting line: arrival order, the concurrency cap, and who gets refused.

These are the only tests in the suite that need real threads, because ordering
between blocked callers is the thing being proved and a single thread can never
be blocked and observed at once. They stay quick by holding the slot rather than
sleeping in it: nothing here waits on a duration it did not have to.
"""

import threading
import time

import pytest

from police_agent.shared.admission import AdmissionQueue, GatekeeperOverloadError
from police_agent.shared.rate_limit import TokenBucket


def queue(concurrency=1, depth=10, capacity=1000.0, refill_rate=1000.0) -> AdmissionQueue:
    """A line whose bucket is generous, so only ordering and slots can block it."""
    return AdmissionQueue(TokenBucket(capacity, refill_rate), concurrency, depth)


def until_waiting(line: AdmissionQueue, count: int, timeout=2.0) -> None:
    """Spin until the background callers have actually reached the line.

    Without this the test races its own threads: a caller that has been started
    has not necessarily queued yet, and asserting on arrival order before
    everyone has arrived would pass or fail on the scheduler's mood.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if line.waiting == count:
            return
        time.sleep(0.005)
    raise AssertionError(f"the queue never reached {count} waiting")


def joiner(line: AdmissionQueue, log: list, name: str) -> threading.Thread:
    """A caller that queues, records the order it got in, and leaves."""

    def run() -> None:
        line.acquire(None)
        log.append(name)
        line.release()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


class TestOverloadQueuesRatherThanVanishing:
    def test_callers_are_admitted_in_the_order_they_arrived(self):
        """First come, first served -- otherwise a waiter can be lapped forever."""
        line = queue(concurrency=1)
        line.acquire(None)  # the test itself holds the only slot
        log: list[str] = []
        threads = []
        for name in ("first", "second", "third"):
            threads.append(joiner(line, log, name))
            until_waiting(line, len(threads))

        line.release()
        for thread in threads:
            thread.join(timeout=2.0)

        assert log == ["first", "second", "third"]

    def test_a_fourth_caller_waits_while_the_agreed_two_are_in_flight(self):
        line = queue(concurrency=2)
        line.acquire(None)
        line.acquire(None)
        log: list[str] = []
        thread = joiner(line, log, "late")
        until_waiting(line, 1)

        assert log == []

        line.release()
        thread.join(timeout=2.0)
        assert log == ["late"]

    def test_waiting_for_a_token_is_a_pause_and_not_a_refusal(self):
        """An empty bucket delays the caller; it never turns it away."""
        line = queue(concurrency=1, capacity=1.0, refill_rate=200.0)
        line.acquire(None)
        line.release()

        line.acquire(None)  # returns once the bucket has refilled

        assert line.queued == 0

    def test_having_to_wait_at_all_is_recorded_for_the_report(self):
        line = queue(concurrency=1)
        line.acquire(None)
        log: list[str] = []
        thread = joiner(line, log, "late")
        until_waiting(line, 1)
        line.release()
        thread.join(timeout=2.0)

        assert line.queued == 1


class TestWhenTheLineIsRefused:
    def test_a_backlog_at_the_agreed_depth_is_refused_rather_than_joined(self):
        line = queue(concurrency=1, depth=1)
        line.acquire(None)
        log: list[str] = []
        joiner(line, log, "filling the line")
        until_waiting(line, 1)

        with pytest.raises(GatekeeperOverloadError, match="queue full"):
            line.acquire(None)

    def test_a_caller_out_of_budget_gives_up_without_poisoning_the_line(self):
        """The ticket must leave with it, or everyone behind it waits on a ghost."""
        line = queue(concurrency=1)
        line.acquire(None)

        with pytest.raises(GatekeeperOverloadError, match="budget"):
            line.acquire(time.monotonic() + 0.05)

        assert line.waiting == 0

    def test_a_deadline_that_has_already_passed_does_not_block_at_all(self):
        line = queue(concurrency=1)
        line.acquire(None)
        started = time.monotonic()

        with pytest.raises(GatekeeperOverloadError):
            line.acquire(started - 1.0)

        assert time.monotonic() - started < 1.0
