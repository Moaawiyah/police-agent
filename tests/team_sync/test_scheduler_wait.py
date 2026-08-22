"""`wait_for_thief_result`: matches the expected settled result, rejects
(without crashing) anything else, and gives up after a bounded wait rather
than blocking forever."""

import queue

import pytest

from police_agent.exceptions import TransportError
from police_agent.team_sync import scheduler_wait


class _Inboxes:
    def __init__(self) -> None:
        self.subgame_results: queue.Queue = queue.Queue()


def test_returns_the_matching_message():
    inboxes = _Inboxes()
    inboxes.subgame_results.put({"series_id": "s1", "sender_role": "thief", "sub_game_number": 2})

    result = scheduler_wait.wait_for_thief_result(inboxes, "s1", 2)

    assert result["sub_game_number"] == 2


def test_rejects_a_mismatched_message_and_keeps_waiting(monkeypatch, capsys):
    monkeypatch.setattr(scheduler_wait, "INBOX_POLL_SECONDS", 0.05)
    inboxes = _Inboxes()
    inboxes.subgame_results.put(
        {"series_id": "wrong-series", "sender_role": "thief", "sub_game_number": 2}
    )
    inboxes.subgame_results.put({"series_id": "s1", "sender_role": "thief", "sub_game_number": 2})

    result = scheduler_wait.wait_for_thief_result(inboxes, "s1", 2)

    assert result["series_id"] == "s1"
    assert "rejected out-of-order" in capsys.readouterr().err


def test_gives_up_after_the_deadline_rather_than_blocking_forever(monkeypatch):
    monkeypatch.setattr(scheduler_wait, "INBOX_POLL_SECONDS", 0.02)
    monkeypatch.setattr(scheduler_wait, "WAIT_FOR_SIBLING_SECONDS", 0.05)
    inboxes = _Inboxes()

    with pytest.raises(TransportError, match="No subgame_result"):
        scheduler_wait.wait_for_thief_result(inboxes, "s1", 2)
