"""The bucket and the detector, on a clock the test owns.

Every test here would otherwise be a test about sleeping. The injected clock is
what makes "wait thirty seconds for a token" a single assignment, and it is also
the only way to prove continuous refill at all: a bucket that only topped up on
a timer tick would pass every test that let real time pass.
"""

from police_agent.shared.rate_limit import DosDetector, TokenBucket


class FakeClock:
    """A monotonic clock the test advances by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def bucket(capacity=3.0, refill_rate=1.0):
    clock = FakeClock()
    return TokenBucket(capacity, refill_rate, clock), clock


class TestTheBucketSpendsAndRefills:
    def test_it_starts_full_so_the_first_call_never_waits(self):
        subject, _ = bucket()

        assert subject.allow() is True
        assert subject.delay_until() == 0.0

    def test_an_empty_bucket_refuses_and_spends_nothing(self):
        subject, _ = bucket(capacity=1.0)
        subject.allow()

        assert subject.allow() is False
        assert subject.tokens == 0.0

    def test_it_refills_continuously_rather_than_in_whole_windows(self):
        """Half a second at one token a second is half a token, not zero."""
        subject, clock = bucket(capacity=3.0, refill_rate=1.0)
        subject.allow(3.0)
        clock.advance(0.5)

        assert subject.delay_until(1.0) == 0.5

    def test_it_never_fills_past_its_capacity(self):
        """An idle hour must not buy an hour's worth of burst."""
        subject, clock = bucket(capacity=3.0, refill_rate=1.0)
        subject.allow(3.0)
        clock.advance(3600.0)

        assert subject.allow(3.0) is True
        assert subject.allow() is False

    def test_it_reports_how_long_a_blocked_caller_would_have_to_wait(self):
        subject, _ = bucket(capacity=2.0, refill_rate=0.5)
        subject.allow(2.0)

        assert subject.delay_until(1.0) == 2.0

    def test_a_bucket_that_never_refills_says_so_instead_of_dividing_by_zero(self):
        subject, _ = bucket(capacity=1.0, refill_rate=0.0)
        subject.allow()

        assert subject.delay_until() == float("inf")


class TestTheDetectorMeasuresRateNotVolume:
    def test_ordinary_traffic_stays_clean(self):
        clock = FakeClock()
        subject = DosDetector(60.0, clock=clock)

        for _ in range(30):
            assert subject.record() is True
            clock.advance(2.0)
        assert subject.tripped is False

    def test_a_burst_trips_it_before_the_minute_is_up(self):
        """The window need not be full for the rate inside it to be indefensible."""
        clock = FakeClock()
        subject = DosDetector(300.0, clock=clock)

        subject.record(200)
        clock.advance(1.0)

        assert subject.record(200) is False

    def test_a_short_window_is_scaled_up_rather_than_read_as_quiet(self):
        """Forty in five seconds is 480 a minute, and must not hide under 300."""
        clock = FakeClock()
        subject = DosDetector(300.0, window_seconds=5.0, clock=clock)

        assert subject.record(40) is False
        assert subject.peak_per_minute == 480.0

    def test_events_that_fall_out_of_the_window_stop_counting(self):
        clock = FakeClock()
        subject = DosDetector(60.0, clock=clock)
        subject.record(50)
        clock.advance(61.0)

        assert subject.record(50) is True
        assert subject.rate_per_minute == 50.0

    def test_once_tripped_it_stays_tripped_however_quiet_it_goes(self):
        """A runaway loop that pauses for breath has not been fixed."""
        clock = FakeClock()
        subject = DosDetector(10.0, clock=clock)
        subject.record(100)
        clock.advance(600.0)

        assert subject.record() is False
        assert subject.snapshot()["tripped"] is True

    def test_the_snapshot_carries_the_line_and_the_worst_reading(self):
        clock = FakeClock()
        subject = DosDetector(10.0, clock=clock)
        subject.record(20)

        assert subject.snapshot() == {
            "tripped": True,
            "limit_per_minute": 10.0,
            "peak_per_minute": 20.0,
        }
