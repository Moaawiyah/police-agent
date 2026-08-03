"""The two measuring instruments the Gatekeeper is built from.

Neither of these decides anything. A bucket says whether a token is available
right now; a detector says how fast traffic is arriving and whether that rate has
ever passed a line. What to *do* about either answer is policy, and policy lives
in `gatekeeper.py` -- which is why the same detector class can lock our outbound
door and, on the inbound side, do nothing but report.

The word "token" here is a rate token and has nothing to do with language-model
tokens; the specification (ch. 9.3.1) is emphatic about not confusing the two,
and the LLM kind is counted in `shared/tokens.py` instead.
"""

import time
from collections import deque


class TokenBucket:
    """Continuous-refill rate limiter (spec ch. 9.3.1, figure 14).

    Refill is computed from elapsed time rather than ticked by a timer: there is
    no scheduler in this process, and a bucket that only refilled while someone
    was watching would hand out a full burst after every idle gap.

    The clock is injected so tests can advance time instead of sleeping through
    it -- a bucket that takes two seconds to refill takes two seconds to test.
    """

    def __init__(self, capacity: float, refill_rate: float, clock=time.monotonic) -> None:
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)  # start full, as the spec's sketch does
        self._clock = clock
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        self.tokens = min(self.capacity, self.tokens + (now - self._last) * self.refill_rate)
        self._last = now

    def allow(self, cost: float = 1.0) -> bool:
        """Spend `cost` and return True, or return False having spent nothing."""
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def delay_until(self, cost: float = 1.0) -> float:
        """Seconds until `cost` could be spent; 0.0 when it can be spent now.

        This is what turns a blocked call into a queued one. Without it the only
        options are to drop the request or to spin asking `allow` again, and the
        scorecard asks for overload to wait its turn rather than disappear.
        """
        self._refill()
        if self.tokens >= cost:
            return 0.0
        if self.refill_rate <= 0.0:
            return float("inf")  # a bucket that never refills never will allow it
        return (cost - self.tokens) / self.refill_rate


class DosDetector:
    """Sliding-window rate anomaly detector (spec ch. 9.3.1, third gate).

    Trips once and stays tripped. A circuit breaker that healed itself would let
    a runaway loop resume the moment it paused for breath, and the failure this
    guards against -- a provider suspending the reporting account -- is not one
    you get to retry. Whoever caused it restarts the process having fixed it.

    Recording stops at the trip, which is also what bounds the window's memory:
    a flood cannot make this deque grow without limit because it stops being fed.
    """

    def __init__(
        self, limit_per_minute: float, window_seconds: float = 60.0, clock=time.monotonic
    ) -> None:
        self.limit_per_minute = float(limit_per_minute)
        self.window_seconds = float(window_seconds)
        self.tripped = False
        self.peak_per_minute = 0.0
        self._clock = clock
        self._events: deque[float] = deque()

    def record(self, count: int = 1) -> bool:
        """Log `count` events and return whether traffic still looks legitimate."""
        if self.tripped:
            return False
        now = self._clock()
        self._events.extend([now] * count)
        cutoff = now - self.window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.popleft()
        self.peak_per_minute = max(self.peak_per_minute, self.rate_per_minute)
        if self.rate_per_minute > self.limit_per_minute:
            self.tripped = True
        return not self.tripped

    @property
    def rate_per_minute(self) -> float:
        """Events in the window, scaled to a per-minute figure.

        Scaled rather than counted, so a short window is not automatically
        innocent: a burst of 200 in five seconds reads as 2400/min, which is what
        it is, instead of hiding under a per-minute threshold it never reached.
        """
        return len(self._events) * 60.0 / self.window_seconds

    def snapshot(self) -> dict:
        """What the match summary and the GUI status line report."""
        return {
            "tripped": self.tripped,
            "limit_per_minute": round(self.limit_per_minute, 1),
            "peak_per_minute": round(self.peak_per_minute, 1),
        }
