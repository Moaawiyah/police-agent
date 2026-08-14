"""The quota as `Gatekeeper`'s first gate, split out of test_quota.py to keep
both files under the project's line budget. See that file's docstring for why
the quota must be checked before anything else runs.
"""

import pytest

from police_agent.shared.gatekeeper import Gatekeeper, GateLimits, QuotaExceededError
from tests.shared.test_quota import TODAY, quota


class TestTheGatekeepersFirstGate:
    def test_a_gate_with_no_quota_is_unaffected(self):
        """Ollama has no daily allowance to protect, and passes nothing."""
        gate = Gatekeeper(_immediate())

        assert gate.submit(lambda: "sent") == "sent"
        assert gate.snapshot()["quota"] is None

    def test_the_allowance_is_spent_by_passing_through(self):
        allowance = quota()
        gate = Gatekeeper(_immediate(), quota=allowance)

        gate.submit(lambda: "sent")

        assert allowance.remaining == 2

    def test_a_spent_day_is_refused_before_any_call_is_made(self):
        """The cheapest question, asked first: no queue, no token, no socket."""
        gate = Gatekeeper(_immediate(), quota=quota(limit=0))

        with pytest.raises(QuotaExceededError):
            gate.submit(_forbidden)

    def test_a_refusal_is_counted_as_one(self):
        gate = Gatekeeper(_immediate(), quota=quota(limit=0))

        with pytest.raises(QuotaExceededError):
            gate.submit(lambda: "sent")

        assert gate.snapshot()["rejected"] == 1

    def test_the_snapshot_reports_the_day_the_report_ran_against(self):
        gate = Gatekeeper(_immediate(), quota=quota())
        gate.submit(lambda: "sent")

        assert gate.snapshot()["quota"] == {"date": TODAY, "spent": 1, "limit": 3}

    def test_retrying_a_failed_call_does_not_re_spend_the_allowance(self):
        """The allowance counts reports; a retry of one report is the same report,
        and `max_retries` is what bounds the calls a submission may make."""
        allowance = quota()
        gate = Gatekeeper(_immediate(), sleep=lambda _seconds: None, quota=allowance)
        attempts: list[int] = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("not yet")
            return "sent"

        assert gate.submit(flaky) == "sent"
        assert (len(attempts), allowance.remaining) == (3, 2)


def _immediate() -> GateLimits:
    """Limits generous enough that only the quota can turn a call away."""
    return GateLimits(requests_per_minute=600, retry_backoff_seconds=0.0)


def _forbidden():
    raise AssertionError("the call was made past a spent quota")
