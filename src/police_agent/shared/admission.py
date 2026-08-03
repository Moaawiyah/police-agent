"""The waiting line in front of the Gatekeeper: who goes next, and when.

Split from `gatekeeper.py` because it is the part with the concurrency in it.
Everything here is about ordering and blocking; the policy questions -- how many
retries, when to lock the door, what gets counted -- are next door, and keeping
them apart is what makes either half readable.

Three conditions have to hold before a call may go out: it must be this caller's
turn, a concurrency slot must be free, and the bucket must have a token. The
first is what makes overload *queue* rather than starve, which the scorecard
asks for by name: without arrival order a caller can be overtaken indefinitely
by later ones and never leave the queue at all.

Only the depth is a hard refusal. A waiting line already `depth` long is not a
busy moment, it is a backlog nothing is draining, and joining it would trade a
prompt error for a slow one.
"""

import itertools
import threading
import time
from collections import deque

from police_agent.exceptions import PoliceAgentError

# Backstop nap for a waiter that is not at the head of the line. Departures
# notify, so this only matters if a notification is ever missed.
_POLL_SECONDS = 1.0


class GatekeeperOverloadError(PoliceAgentError):
    """The waiting line was full, or the caller's budget ran out inside it."""


class AdmissionQueue:
    """FIFO admission control over a token bucket and a concurrency cap."""

    def __init__(self, bucket, concurrency: int, depth: int, clock=time.monotonic) -> None:
        self._bucket = bucket
        self._concurrency = max(1, int(concurrency))
        self._depth = max(1, int(depth))
        self._clock = clock
        self._gate = threading.Condition()
        self._waiting: deque[int] = deque()
        self._tickets = itertools.count()
        self._in_flight = 0
        self.queued = 0  # how often a caller had to wait, for the report

    @property
    def waiting(self) -> int:
        """How many callers are standing in the line right now."""
        return len(self._waiting)

    def acquire(self, deadline: float | None) -> None:
        """Block until this caller may call out, or refuse to let it wait.

        `deadline` is an absolute monotonic time, or None for "wait as long as
        the limits require". A caller with a deadline is turned away rather than
        released late: a taunt that arrives after the turn it belonged to is
        worse than no taunt, because the turn was spent waiting for it.
        """
        with self._gate:
            if len(self._waiting) >= self._depth:
                raise GatekeeperOverloadError(f"Gatekeeper queue full ({self._depth} waiting)")
            ticket = next(self._tickets)
            self._waiting.append(ticket)
            if len(self._waiting) > 1 or self._in_flight >= self._concurrency:
                self.queued += 1
            while (nap := self._admit(ticket)) > 0.0:
                if deadline is not None and self._clock() >= deadline:
                    self._waiting.remove(ticket)
                    self._gate.notify_all()
                    raise GatekeeperOverloadError("Gatekeeper: no slot within the caller's budget")
                self._gate.wait(timeout=self._capped(nap, deadline))

    def release(self) -> None:
        """Give the slot back and wake whoever is next."""
        with self._gate:
            self._in_flight -= 1
            self._gate.notify_all()

    def _admit(self, ticket: int) -> float:
        """Claim the slot if it is this ticket's turn, else how long to nap for.

        Head-of-line is checked before the bucket, so a latecomer cannot spend
        the token the caller in front of it has been waiting for.
        """
        if self._waiting[0] != ticket or self._in_flight >= self._concurrency:
            return _POLL_SECONDS
        nap = self._bucket.delay_until()
        if nap > 0.0:
            return nap
        self._bucket.allow()
        self._waiting.popleft()
        self._in_flight += 1
        return 0.0

    def _capped(self, nap: float, deadline: float | None) -> float:
        """Never sleep past the caller's deadline, however long the nap wanted to be."""
        return nap if deadline is None else max(0.0, min(nap, deadline - self._clock()))
