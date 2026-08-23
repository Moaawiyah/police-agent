"""`CoordinatorInboxes`, split out of `coordinator.py` to keep it inside the
project's 150-line budget. The mailboxes are plain state -- worth reading on
their own, apart from the FastMCP tool wiring that fills them.
"""

import queue
import threading


class CoordinatorInboxes:
    """The mailboxes the sibling Thief process fills; the scheduler drains them."""

    def __init__(self) -> None:
        """Two empty mailboxes: settled results, and best-effort acks of ours."""
        self.subgame_results: queue.Queue = queue.Queue()
        self.acks: queue.Queue = queue.Queue()
        self.series_start: queue.Queue = queue.Queue()
        self.handoff: queue.Queue = queue.Queue()
        self.series_complete: queue.Queue = queue.Queue()
        self._seen_message_ids: set[str] = set()
        self._seen_lock = threading.Lock()

    def first_delivery(self, message: dict) -> bool:
        """Deduplicate transport retries before they reach the scheduler."""
        message_id = str(message.get("message_id", ""))
        if not message_id:
            return True
        with self._seen_lock:
            if message_id in self._seen_message_ids:
                return False
            self._seen_message_ids.add(message_id)
            return True

    def clear(self) -> None:
        """Discard queued messages from a failed attempt before a fresh one."""
        for inbox in (
            self.subgame_results,
            self.acks,
            self.series_start,
            self.handoff,
            self.series_complete,
        ):
            while not inbox.empty():
                inbox.get_nowait()
        with self._seen_lock:
            self._seen_message_ids.clear()
