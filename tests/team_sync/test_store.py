"""Atomic persistence: state survives a rebuild, dedup and the email marker
are idempotent, and a crash mid-write cannot corrupt what was there before.
"""

import json

from police_agent.team_sync.state import SeriesSyncState, SeriesSyncStatus
from police_agent.team_sync.store import TeamSyncStore


def test_a_fresh_store_has_no_persisted_status(tmp_path):
    store = TeamSyncStore(tmp_path)

    assert store.load_status() is None


def test_save_then_load_round_trips_the_status(tmp_path):
    store = TeamSyncStore(tmp_path)
    status = SeriesSyncStatus(series_id="s1", sub_game_number=3, state=SeriesSyncState.PLAYING)

    store.save_status(status)

    assert store.load_status() == status


def test_resuming_after_a_restart_finds_the_same_state():
    """Kill and rebuild the store object from disk: it must pick up where it
    left off, per the plan's resume-from-persisted-state requirement."""
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        first = TeamSyncStore(directory)
        first.save_status(
            SeriesSyncStatus(series_id="s1", sub_game_number=4, state=SeriesSyncState.READY)
        )
        del first  # simulate the process dying

        second = TeamSyncStore(directory)  # a brand new object, same directory
        resumed = second.load_status()

        assert resumed is not None
        assert (resumed.sub_game_number, resumed.state) == (4, SeriesSyncState.READY)


def test_a_message_is_only_seen_once_it_is_marked(tmp_path):
    store = TeamSyncStore(tmp_path)
    key = "s1|2|thief|abc123"

    assert store.seen(key) is False
    store.mark_seen(key)
    assert store.seen(key) is True


def test_marking_the_same_key_twice_does_not_duplicate_it(tmp_path):
    store = TeamSyncStore(tmp_path)
    key = "s1|2|thief|abc123"

    store.mark_seen(key)
    store.mark_seen(key)

    raw = json.loads((tmp_path / "team_sync_seen.json").read_text())
    assert raw.count(key) == 1


def test_email_sent_is_false_until_marked(tmp_path):
    store = TeamSyncStore(tmp_path)

    assert store.email_sent("game-1", "hash-a") is False
    store.mark_email_sent("game-1", "hash-a")
    assert store.email_sent("game-1", "hash-a") is True


def test_email_sent_is_scoped_to_the_exact_report_hash(tmp_path):
    """A retried delivery with a different (e.g. corrected) hash is not
    mistaken for the one already mailed."""
    store = TeamSyncStore(tmp_path)
    store.mark_email_sent("game-1", "hash-a")

    assert store.email_sent("game-1", "hash-b") is False


def test_reset_clears_the_persisted_status(tmp_path):
    store = TeamSyncStore(tmp_path)
    store.save_status(SeriesSyncStatus(series_id="s1"))

    store.reset()

    assert store.load_status() is None


def test_reset_series_clears_attempt_bookkeeping_but_keeps_artifacts(tmp_path):
    store = TeamSyncStore(tmp_path)
    store.save_status(SeriesSyncStatus(series_id="s1"))
    store.mark_seen("s1|1|thief|m1")
    store.mark_email_sent("g1", "hash")
    artifact = tmp_path / "log_g1_g01.json"
    artifact.write_text("{}")

    store.reset_series()

    assert store.load_status() is None
    assert not (tmp_path / "team_sync_seen.json").exists()
    assert not (tmp_path / "team_sync_email.json").exists()
    assert artifact.exists()


def test_no_tmp_file_is_left_behind_after_a_save(tmp_path):
    store = TeamSyncStore(tmp_path)
    store.save_status(SeriesSyncStatus(series_id="s1"))

    assert not (tmp_path / "team_sync_state.json.tmp").exists()
    assert (tmp_path / "team_sync_state.json").exists()
