"""The daily quota: ch. 9.3.1's *first* gate, ahead of the bucket.

Figure 13 draws three gates a request crosses -- quota manager, token bucket,
anomaly detector -- and until now this repository had two. The bucket bounds how
fast calls leave; it says nothing about how many leave in a day, and those are
different failures. A provider's daily allowance is exhausted by a slow, polite
loop just as surely as by a burst, and the sanction ch. 9.3.1 warns about is not
a 429 to back off from but an account the lecturer's report cannot be sent from.

Counted across process restarts, which is the only thing that makes it a *daily*
quota: a sub-game is its own process (ch. 2.4.2), so a counter living in memory
would reset every game and a series of twenty would report a spend of one. The
ledger is a small JSON file, and a day rolls over by comparing dates rather than
by scheduling anything -- there is no timer in this process to schedule it with.

Deliberately generic: it counts calls, not mail. `infra/gmail.py` supplies the
limit and the file, and the Gatekeeper spends it for whoever is passing through.

Failure to *read* the ledger is not failure to spend. A corrupt or unreadable
file is treated as an empty day, because the alternative -- refusing to send --
turns a damaged local file into rule 35's "no report, no points for either team".
The opposite failure, over-sending, costs a 429 and a backoff.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from police_agent.exceptions import PoliceAgentError

__all__ = ["DailyQuota", "QuotaExceededError"]


class QuotaExceededError(PoliceAgentError):
    """Today's allowance is spent. Not a transient failure, and not retryable."""


def _today() -> str:
    """The current UTC date, as the ledger writes it.

    UTC rather than local time so a laptop carried across a timezone does not
    grant itself a second allowance, and so two peers reading the same file --
    which they never do, but which is the sort of thing that changes -- would
    agree about when the day turned over.
    """
    return datetime.now(UTC).date().isoformat()


class DailyQuota:
    """A counter of calls made today, persisted so a restart does not forget."""

    def __init__(self, limit: int, path: str | Path | None = None, today=_today) -> None:
        """A `limit`-call daily allowance, loading today's tally from `path` if one exists."""
        self.limit = int(limit)
        self.path = Path(path) if path else None
        self._today = today
        self._date, self._count = self._load()

    def spend(self, cost: int = 1) -> None:
        """Book `cost` against today, or refuse the call outright.

        Refuses *before* spending, so a caller that was turned away has not
        quietly consumed part of the allowance it was denied.
        """
        self._roll_over()
        if self._count + cost > self.limit:
            raise QuotaExceededError(
                f"Daily quota exhausted: {self._count}/{self.limit} calls already made "
                f"on {self._date}. It resets at midnight UTC."
            )
        self._count += cost
        self._save()

    @property
    def remaining(self) -> int:
        """How many calls remain in today's allowance."""
        self._roll_over()
        return max(0, self.limit - self._count)

    def snapshot(self) -> dict:
        """What the match summary reports as evidence the first gate was there."""
        self._roll_over()
        return {"date": self._date, "spent": self._count, "limit": self.limit}

    def _roll_over(self) -> None:
        """A new day is a fresh allowance, noticed on use rather than on a timer."""
        if self._date != self._today():
            self._date, self._count = self._today(), 0

    def _load(self) -> tuple[str, int]:
        """Today's tally from the ledger, or an empty day if there is no reading."""
        if self.path is None or not self.path.is_file():
            return self._today(), 0
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            return str(stored["date"]), int(stored["count"])
        except (OSError, ValueError, KeyError, TypeError):
            return self._today(), 0

    def _save(self) -> None:
        """Write the tally, or carry on having failed to.

        A ledger that could not be written is a worse day's accounting, not a
        reason to abandon the send it was counting.
        """
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"date": self._date, "count": self._count}), encoding="utf-8"
            )
        except OSError:
            return
