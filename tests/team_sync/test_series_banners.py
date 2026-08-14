"""What the window is told during a six-sub-game team_sync series.

Separate from `test_full_series.py` (which is about what the series
produces) because the failure they catch is different: nothing here changes
a result, an artifact or a score -- it changes what somebody watching the
match believes is happening.
"""

from tests.team_sync.conftest import TOTAL, run


def test_the_gui_is_told_who_is_playing_each_subgame(police, tmp_path, monkeypatch):
    """A sub-game this process does not own still reports progress."""
    _summaries, events, _mailed, _sibling = run(police, tmp_path, monkeypatch)

    states = [
        (event["state"], event["sub_game_number"])
        for event in events
        if event["type"] == "team_sync"
    ]
    assert ("WAITING", 2) in states  # the sibling owns sub-game 2
    assert ("READY", 3) in states  # ...and Police is unlocked for sub-game 3
    assert ("SERIES_COMPLETE", TOTAL) in states


def test_a_sibling_owned_subgame_reads_as_waiting_until_its_result_lands(
    police, tmp_path, monkeypatch
):
    """AUDITING must not label the wait itself.

    The sibling's sub-game takes as long as any other, and announcing
    AUDITING before the result arrives left the window reading "AUDITING
    SUBGAME 2" for the whole of it -- work this process is not doing, on a
    game it did not play.
    """
    _summaries, events, _mailed, _sibling = run(police, tmp_path, monkeypatch)

    second = [
        event["state"]
        for event in events
        if event["type"] == "team_sync" and event["sub_game_number"] == 2
    ]
    assert second == ["WAITING", "WAITING", "waiting_for_sibling", "AUDITING", "SETTLED"]
