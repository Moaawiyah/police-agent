"""The Gatekeeper: the single door every call to an external API leaves by.

Appendix He 28 and 29 make the token bucket and the DOS detector mandatory, and
ch. 11 scores the pattern itself: one central chokepoint doing rate limiting,
queueing, retry and logging, with nothing slipping past it. Figure 13 draws the
three gates a request crosses -- quota, bucket, anomaly detector -- and this is
that chain. The quota is optional because only one caller has a daily allowance
to protect: the local Ollama server has none, and the Gmail reporter supplies its
own (`shared/quota.py`).

**What goes through it.** Outbound calls to somebody else's service. Today the
only one is the local Ollama server behind `infra/ollama.py`; the Gmail reporting
client the specification is really aiming at (ch. 9.3) is not built yet, and when
it is it needs nothing new here -- it hands `submit` a callable like everyone
else and inherits the bucket, the queue and the retries already configured.

**What deliberately does not.** The peer-to-peer MCP transport. Those messages
are our own turns going to the opponent, not requests against a third party's
quota, and there is no 429 waiting at the other end. Throttling them would only
delay a turn the opponent is timing with its watchdog, which is a technical loss
(ch. 2.4.2) traded for a protection nobody asked for. `infra/mcp_client.py`
therefore calls out directly, on purpose.

Retries are bounded by `max_retries` as a *ceiling*, not a quota to be spent: a
call given a budget stops retrying once the next backoff would overrun it. The
agreed value is a minimum the code must never fall below (Appendix Vav status
"minimum"), which constrains what may be *configured* -- not how long a caller
holding a turn open is obliged to keep trying.
"""

import time
from dataclasses import asdict, dataclass

from police_agent.exceptions import PoliceAgentError
from police_agent.shared.admission import AdmissionQueue, GatekeeperOverloadError
from police_agent.shared.quota import QuotaExceededError
from police_agent.shared.rate_limit import DosDetector, TokenBucket

# How far above the agreed request rate our own outbound traffic must run before
# it reads as a bug rather than a busy game. At the shipped 30/min this is 300
# attempts a minute -- five a second, sustained, out of a turn-based agent whose
# turns are seconds apart. Nothing legitimate in this process comes close.
DOS_ANOMALY_MULTIPLE = 10

__all__ = [
    "GateLimits",
    "Gatekeeper",
    "GatekeeperLockedError",
    "GatekeeperOverloadError",
    "QuotaExceededError",
]


class GatekeeperLockedError(PoliceAgentError):
    """The DOS detector tripped: this process is refusing to call out at all."""


@dataclass(frozen=True)
class GateLimits:
    """Appendix Vav table 19, whose example values are the defaults it demands.

    Status "minimum" means the two teams may negotiate these upwards but never
    below the examples, and that absent an explicit agreement the code must use
    the examples -- hence real defaults here rather than `None` and a crash.
    """

    requests_per_minute: int = 30
    concurrent_requests: int = 2
    retry_backoff_seconds: float = 5.0
    max_retries: int = 3
    queue_depth: int = 100

    @classmethod
    def from_getter(cls, get) -> "GateLimits":
        """Read the limits from a `config.get`-shaped callable.

        `or` rather than a bare default: a key present but null or zero means the
        agreed file did not choose, and must land on the Appendix Vav example.
        """
        return cls(
            requests_per_minute=int(get("gatekeeper.requests_per_minute") or 30),
            concurrent_requests=int(get("gatekeeper.concurrent_requests") or 2),
            retry_backoff_seconds=float(get("gatekeeper.retry_backoff_seconds") or 5.0),
            max_retries=int(get("gatekeeper.max_retries") or 3),
            queue_depth=int(get("gatekeeper.queue_depth") or 100),
        )


class Gatekeeper:
    """Admits outbound API calls one agreed rate token at a time."""

    def __init__(
        self,
        limits: GateLimits | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        quota=None,
    ):
        self.limits = limits or GateLimits()
        self.quota = quota
        rate = self.limits.requests_per_minute
        self._bucket = TokenBucket(rate, rate / 60.0, clock)
        self._queue = AdmissionQueue(
            self._bucket, self.limits.concurrent_requests, self.limits.queue_depth, clock
        )
        self.dos = DosDetector(rate * DOS_ANOMALY_MULTIPLE, clock=clock)
        self._sleep = sleep
        self._clock = clock
        self.counts = dict.fromkeys(("submitted", "sent", "retried", "rejected", "failed"), 0)

    @classmethod
    def from_config(cls, config=None) -> "Gatekeeper":
        """The gate this peer's agreed `game.json` describes."""
        get = config.get if config is not None else (lambda _key, default=None: default)
        return cls(GateLimits.from_getter(get))

    def submit(self, call, budget: float | None = None):
        """Run `call` behind the gate, returning whatever it returns.

        `budget` is the caller's whole allowance in seconds -- queueing, the call
        itself and every retry all come out of the one deadline. Omit it and the
        call waits as long as the limits require, which is what an end-of-game
        report should do and what a taunt sharing its turn with the opponent's
        watchdog must not.
        """
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
        """What the match summary reports as evidence the gate was in the path."""
        return {
            "limits": asdict(self.limits),
            **self.counts,
            "queued": self._queue.queued,
            "quota": self.quota.snapshot() if self.quota is not None else None,
            "dos": self.dos.snapshot(),
        }

    def _spend_quota(self) -> None:
        """The first gate: is there any allowance left today at all (ch. 9.3.1)?

        Ahead of everything else because it is the cheapest question and the one
        with no remedy: a call the bucket delays goes out a second later, and a
        call past the daily allowance does not go out today. Spent once per
        submission rather than once per attempt -- the allowance counts reports,
        and a retry of the same report is the same report; `max_retries` is what
        bounds the calls one submission may make.
        """
        if self.quota is None:
            return
        try:
            self.quota.spend()
        except QuotaExceededError:
            self.counts["rejected"] += 1
            raise

    def _check_lock(self) -> None:
        """The third gate: a runaway caller loses the door entirely (ch. 9.3.1)."""
        if self.dos.record():
            return
        self.counts["rejected"] += 1
        raise GatekeeperLockedError(
            f"Gatekeeper locked: outbound rate reached {self.dos.peak_per_minute:.0f}/min, "
            f"above the {self.dos.limit_per_minute:.0f}/min anomaly threshold"
        )

    def _attempt(self, call, deadline: float | None):
        """Call, and keep calling on failure until the ceiling or the budget stops us."""
        failure: Exception = RuntimeError("gatekeeper made no attempt")
        for attempt in range(self.limits.max_retries + 1):
            try:
                result = call()
            except Exception as exc:  # noqa: BLE001 - retried, then re-raised as it came
                failure = exc
                self.counts["failed"] += 1
            else:
                self.counts["sent"] += 1
                return result
            if attempt == self.limits.max_retries or not self._backoff(deadline):
                break
            self.counts["retried"] += 1
        raise failure

    def _backoff(self, deadline: float | None) -> bool:
        """Wait out the retry delay and buy the next attempt's token, if there is time.

        A retry is another request against the same quota, so it pays for a token
        like any other; the pause is whichever of the two is longer.
        """
        pause = max(self.limits.retry_backoff_seconds, self._bucket.delay_until())
        if deadline is not None and self._clock() + pause > deadline:
            return False
        self._sleep(pause)
        self._bucket.allow()
        return True
