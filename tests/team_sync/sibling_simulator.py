"""A stand-in for the SEPARATE thief_agent process, for whole-series flow tests.

CLAUDE.md forbids thief agent logic in this repo, so this is deliberately not
a thief: it never moves a piece and never runs a game. It speaks only the
team_sync wire -- `ack`, `subgame_result`, `handoff` -- answering each envelope
Police sends the way the sibling repo's coordinator would, and hands back
pre-built settled payloads for the sub-games that repo owns.

Every reply is signed with the production `security.sign_message`, so what the
scheduler drains from these queues is shaped exactly like what a real
coordinator would have queued for it.
"""

import queue

from police_agent.team_sync import security
from police_agent.team_sync.import_adapter import compute_result_hash
from police_agent.team_sync.messages import Ack, SubgameHandoff, new_message_id
from police_agent.team_sync.state import THIEF, role_for_subgame
from tests.team_sync.helpers import settled_payload


class SimulatedInboxes:
    """The same five mailboxes `coordinator.CoordinatorInboxes` exposes."""

    def __init__(self) -> None:
        self.subgame_results: queue.Queue = queue.Queue()
        self.acks: queue.Queue = queue.Queue()
        self.series_start: queue.Queue = queue.Queue()
        self.handoff: queue.Queue = queue.Queue()
        self.series_complete: queue.Queue = queue.Queue()


def thief_result(sub_game_number: int, series_id: str, total: int, start_role: str) -> dict:
    """One settled sub-game as the sibling exports it, schedule fields included."""
    payload = settled_payload(sub_game_number, series_id=series_id)
    payload["message_id"] = new_message_id()
    # The sibling played thief and was caught: in a capture the cop wins, and
    # the totals score the (result, role) pair rather than this label alone.
    payload["winner"] = "police"
    payload["terms"] = {"num_games": total}
    payload["start_role"] = start_role
    payload["completed_subgame"] = sub_game_number
    payload["next_subgame"] = sub_game_number + 1
    payload["next_role"] = role_for_subgame(sub_game_number + 1, start_role)
    payload["result_hash"] = compute_result_hash(payload)
    return payload


class SiblingThiefProcess:
    """Police's view of the sibling process: an outbound client that answers.

    Stands in for `client.TeamSyncClient`, so every call the scheduler makes
    lands here; the reply the real sibling would push back over its own link
    is queued on `inboxes` instead of crossing a socket.
    """

    def __init__(self, inboxes: SimulatedInboxes, secret: str, total: int, start_role: str) -> None:
        """Answer for a `total`-sub-game series opened by `start_role`."""
        self.inboxes = inboxes
        self.secret = secret
        self.total = total
        self.start_role = start_role
        self.received: list[tuple] = []  # what Police sent us, in order
        self.last_message_id = ""

    def _sent(self, kind: str, sub_game_number: int) -> None:
        """Record one inbound envelope and mint the id Police expects acked."""
        self.last_message_id = new_message_id()
        self.received.append((kind, sub_game_number))

    def _queue(self, inbox: queue.Queue, message: dict) -> None:
        inbox.put(security.sign_message(message, self.secret))

    def _ack(self, series_id: str, sub_game_number: int) -> None:
        """Acknowledge the envelope just received, as the sibling does on delivery."""
        ack = Ack(
            series_id=series_id,
            ack_for_message_id=self.last_message_id,
            sub_game_number=sub_game_number,
            sender_role=THIEF,
        )
        self._queue(self.inboxes.acks, ack.to_dict())

    def _settle(self, series_id: str, number: int) -> None:
        """Report the sub-game the sibling owns, then unlock Police's next one."""
        self._queue(
            self.inboxes.subgame_results,
            thief_result(number, series_id, self.total, self.start_role),
        )
        if number >= self.total:
            return
        handoff = SubgameHandoff(
            series_id=series_id,
            completed_subgame=number,
            next_subgame=number + 1,
            sub_game_number=number + 1,
            sender_role=THIEF,
            start_role=self.start_role,
            next_role=role_for_subgame(number + 1, self.start_role),
        )
        self._queue(self.inboxes.handoff, handoff.to_dict())

    def send_series_start(self, series_id, game_id, total, first, **_kwargs) -> dict:
        """Police opened the series: acknowledge, and join sub-game 1."""
        self._sent("series_start", first)
        self._ack(series_id, first)
        return {"ok": True}

    def send_handoff(self, series_id, completed, next_subgame, **_kwargs) -> dict:
        """Police settled its sub-game: acknowledge, then play ours if it is ours."""
        self._sent("handoff", next_subgame)
        self._ack(series_id, next_subgame)
        if role_for_subgame(next_subgame, self.start_role) == THIEF:
            self._settle(series_id, next_subgame)
        return {"ok": True}

    def send_ack(self, series_id, ack_for_message_id, sub_game_number) -> dict:
        """Police acknowledged one of our handoffs."""
        self._sent("ack", sub_game_number)
        return {"ok": True}

    def send_series_complete(self, series_id, result=None) -> dict:
        """Police filed the binding report for the whole series."""
        self._sent("series_complete", self.total)
        return {"ok": True}


def install(monkeypatch, scheduler, secret: str, total: int, start_role: str = "police"):
    """Point `scheduler` at a simulated sibling instead of a real localhost link."""
    inboxes = SimulatedInboxes()
    sibling = SiblingThiefProcess(inboxes, secret, total, start_role)
    monkeypatch.setattr(
        scheduler.ts_coordinator,
        "start_coordinator",
        lambda host, port, secret_, provider: (inboxes, None),
    )
    monkeypatch.setattr(scheduler.ts_client, "TeamSyncClient", lambda url, secret_, **kw: sibling)
    return sibling
