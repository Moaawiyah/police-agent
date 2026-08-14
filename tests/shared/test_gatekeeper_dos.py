"""The DOS lock (ch. 9.3.1's third gate), and what the report can see, split
out of test_gatekeeper.py to keep both files under the project's line budget.
"""

import pytest

from police_agent.exceptions import PoliceAgentError
from police_agent.shared.gatekeeper import GatekeeperLockedError, GatekeeperOverloadError
from tests.shared.test_gatekeeper import explode, gate


class TestTheDosGateLocksTheDoor:
    """The third gate (ch. 9.3.1), reached when refusals come back fast.

    A single-threaded runaway never gets here: the bucket makes it wait, which is
    the cheaper cure. What does get here is a caller looping on rejections --
    several threads against a full queue -- so the detector is fed by hand below
    rather than through a flood the bucket would have throttled anyway.
    """

    def test_a_runaway_caller_is_cut_off_from_the_api_entirely(self):
        subject, _ = gate(requests_per_minute=30)
        subject.dos.record(400)  # ten times the agreed rate: a loop, not a game

        with pytest.raises(GatekeeperLockedError, match="anomaly threshold"):
            subject.submit(lambda: None)

    def test_the_lock_does_not_lift_once_the_flood_stops(self):
        subject, _ = gate(requests_per_minute=30)
        subject.dos.record(400)
        with pytest.raises(GatekeeperLockedError):
            subject.submit(lambda: None)

        with pytest.raises(GatekeeperLockedError):
            subject.submit(lambda: None)

    def test_a_locked_gate_never_reaches_the_call_at_all(self):
        subject, _ = gate(requests_per_minute=30)
        subject.dos.record(400)
        called = []

        with pytest.raises(GatekeeperLockedError):
            subject.submit(lambda: called.append(1))

        assert called == []

    def test_every_refusal_is_one_kind_of_error_the_caller_can_catch(self):
        """Both gates raise under `PoliceAgentError`, like the rest of the agent."""
        assert issubclass(GatekeeperLockedError, PoliceAgentError)
        assert issubclass(GatekeeperOverloadError, PoliceAgentError)


class TestWhatTheReportCanSee:
    def test_the_snapshot_carries_the_limits_that_were_actually_applied(self):
        subject, _ = gate(requests_per_minute=45, queue_depth=7)

        snapshot = subject.snapshot()

        assert snapshot["limits"]["requests_per_minute"] == 45
        assert snapshot["limits"]["queue_depth"] == 7

    def test_it_counts_what_went_out_and_what_did_not(self):
        subject, _ = gate(max_retries=1)
        subject.submit(lambda: "fine")
        with pytest.raises(ConnectionError):
            subject.submit(explode())

        snapshot = subject.snapshot()

        assert (snapshot["submitted"], snapshot["sent"], snapshot["failed"]) == (2, 1, 2)
        assert snapshot["queued"] == 0
        assert snapshot["dos"]["tripped"] is False

    def test_a_locked_gate_shows_up_as_a_rejection_and_a_tripped_detector(self):
        subject, _ = gate(requests_per_minute=30)
        subject.dos.record(400)
        with pytest.raises(GatekeeperLockedError):
            subject.submit(lambda: None)

        snapshot = subject.snapshot()

        assert snapshot["dos"]["tripped"] is True
        assert snapshot["rejected"] == 1
