"""Implementation of the outbound API gate.

The public compatibility module is :mod:`gatekeeper`; this file keeps the
limits and the retrying gate together without making that facade oversized.
"""

import time
from dataclasses import asdict, dataclass

from police_agent.exceptions import PoliceAgentError
from police_agent.shared.admission import AdmissionQueue, GatekeeperOverloadError
from police_agent.shared.quota import QuotaExceededError
from police_agent.shared.rate_limit import DosDetector, TokenBucket

DOS_ANOMALY_MULTIPLE = 10


class GatekeeperLockedError(PoliceAgentError):
    """The DOS detector tripped and outbound calls are disabled."""


@dataclass(frozen=True)
class GateLimits:
    """The agreed minimum limits for outbound model and reporting calls."""

    requests_per_minute: int = 30
    concurrent_requests: int = 2
    retry_backoff_seconds: float = 5.0
    max_retries: int = 3
    queue_depth: int = 100

    @classmethod
    def from_getter(cls, get) -> "GateLimits":
        """Build from a `config.get`-shaped getter, falling back to these defaults."""
        return cls(
            requests_per_minute=int(get("gatekeeper.requests_per_minute") or 30),
            concurrent_requests=int(get("gatekeeper.concurrent_requests") or 2),
            retry_backoff_seconds=float(get("gatekeeper.retry_backoff_seconds") or 5.0),
            max_retries=int(get("gatekeeper.max_retries") or 3),
            queue_depth=int(get("gatekeeper.queue_depth") or 100),
        )


class Gatekeeper:
    """Admit, retry, count and report one outbound call at a time."""

    def __init__(self, limits=None, sleep=time.sleep, clock=time.monotonic, quota=None):
        """Build the bucket, admission queue and DOS detector from `limits`."""
        self.limits = limits or GateLimits()
        self.quota = quota
        rate = self.limits.requests_per_minute
        self._bucket = TokenBucket(rate, rate / 60.0, clock)
        self._queue = AdmissionQueue(
            self._bucket, self.limits.concurrent_requests, self.limits.queue_depth, clock
        )
        self.dos = DosDetector(rate * DOS_ANOMALY_MULTIPLE, clock=clock)
        self._sleep, self._clock = sleep, clock
        self.counts = dict.fromkeys(("submitted", "sent", "retried", "rejected", "failed"), 0)

    @classmethod
    def from_config(cls, config=None) -> "Gatekeeper":
        """Build a Gatekeeper from the agreed `gatekeeper.*` config keys."""
        get = config.get if config is not None else (lambda _key, default=None: default)
        return cls(GateLimits.from_getter(get))

    def submit(self, call, budget=None):
        """Admit, attempt (with retries) and count one outbound `call`."""
        self.counts["submitted"] += 1
        self._spend_quota()
        self._check_lock()
        deadline = None if budget is None else self._clock() + budget
        try:
            self._queue.acquire(deadline)
        except GatekeeperOverloadError:
            self.counts["rejected"] += 1
            raise
        try:
            return self._attempt(call, deadline)
        finally:
            self._queue.release()

    def snapshot(self) -> dict:
        """What the match summary and the GUI status line report."""
        return {
            "limits": asdict(self.limits),
            **self.counts,
            "queued": self._queue.queued,
            "quota": self.quota.snapshot() if self.quota is not None else None,
            "dos": self.dos.snapshot(),
        }

    def _spend_quota(self) -> None:
        if self.quota is None:
            return
        try:
            self.quota.spend()
        except QuotaExceededError:
            self.counts["rejected"] += 1
            raise

    def _check_lock(self) -> None:
        if self.dos.record():
            return
        self.counts["rejected"] += 1
        raise GatekeeperLockedError(
            f"Gatekeeper locked: outbound rate reached {self.dos.peak_per_minute:.0f}/min, "
            f"above the {self.dos.limit_per_minute:.0f}/min anomaly threshold"
        )

    def _attempt(self, call, deadline):
        failure: Exception = RuntimeError("gatekeeper made no attempt")
        for attempt in range(self.limits.max_retries + 1):
            try:
                result = call()
            except Exception as exc:  # noqa: BLE001 - bounded retry policy
                failure = exc
                self.counts["failed"] += 1
            else:
                self.counts["sent"] += 1
                return result
            if attempt == self.limits.max_retries or not self._backoff(deadline):
                break
            self.counts["retried"] += 1
        raise failure

    def _backoff(self, deadline) -> bool:
        pause = max(self.limits.retry_backoff_seconds, self._bucket.delay_until())
        if deadline is not None and self._clock() + pause > deadline:
            return False
        self._sleep(pause)
        self._bucket.allow()
        return True


__all__ = [
    "DOS_ANOMALY_MULTIPLE",
    "GateLimits",
    "Gatekeeper",
    "GatekeeperLockedError",
    "GatekeeperOverloadError",
    "QuotaExceededError",
]
