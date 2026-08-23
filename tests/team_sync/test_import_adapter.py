"""Importing a settled Thief sub-game: validation, dedup, and the
all-sub-games-present, once-only email gate.
"""

import pytest

from police_agent.exceptions import CryptoError, ProtocolError
from police_agent.sdk import PoliceAgentSDK
from police_agent.team_sync import import_adapter
from police_agent.team_sync.store import TeamSyncStore
from tests.conftest import config_with
from tests.team_sync.helpers import police_summary, settled_payload


def _agent(tmp_path, **overrides):
    agent = PoliceAgentSDK(config=config_with(game__num_games=2, **overrides))
    calls = []
    agent.email_report = lambda paths: calls.append(paths) or "stubbed"
    return agent, calls


def test_import_and_persist_writes_artifacts_and_returns_thief_shaped_summary(tmp_path):
    agent, _ = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")
    payload = settled_payload(2)

    summary = import_adapter.import_and_persist(payload, agent, tmp_path, store)

    assert summary["role"] == "thief"
    assert summary["result"] == "capture"
    written = tmp_path / "OURTEAM" / "record_ourteam-vs-theirteam_g02.json"
    if not written.is_file():
        import sys

        print("DEBUG tmp_path=", tmp_path, file=sys.stderr)
        print("DEBUG tmp_path contents=", list(tmp_path.rglob("*")), file=sys.stderr)
        print("DEBUG summary identity=", summary.get("identity"), file=sys.stderr)
    assert written.is_file()


def test_a_retried_delivery_does_not_write_or_email_twice(tmp_path):
    agent, calls = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")
    agent.write_artifacts(police_summary(1), tmp_path)  # sub-game 1 already on file
    payload = settled_payload(2)

    import_adapter.import_and_persist(payload, agent, tmp_path, store)
    import_adapter.import_and_persist(payload, agent, tmp_path, store)

    assert len(calls) == 1


def test_email_does_not_fire_until_every_subgame_is_on_file(tmp_path):
    agent, calls = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")

    import_adapter.import_and_persist(settled_payload(2), agent, tmp_path, store)

    assert calls == []  # sub-game 1 was never filed


def test_email_fires_once_every_agreed_subgame_is_on_file(tmp_path):
    agent, calls = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")
    agent.write_artifacts(police_summary(1), tmp_path)

    import_adapter.import_and_persist(settled_payload(2), agent, tmp_path, store)

    assert len(calls) == 1


def test_a_tamper_forfeit_subgame_is_still_emailed(tmp_path):
    """The gate is 'every sub-game has a terminal artifact', not 'every audit passed'."""
    agent, calls = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")
    agent.write_artifacts(police_summary(1), tmp_path)

    import_adapter.import_and_persist(
        settled_payload(2, result="tamper_forfeit"), agent, tmp_path, store
    )

    assert len(calls) == 1


def test_a_malformed_payload_is_rejected(tmp_path):
    agent, _ = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")
    payload = settled_payload(2)
    del payload["identity"]

    with pytest.raises(ProtocolError):
        import_adapter.import_and_persist(payload, agent, tmp_path, store)


def test_a_corrupted_result_hash_is_rejected(tmp_path):
    agent, _ = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")
    payload = settled_payload(2)
    payload["result_hash"] = "0" * 64

    with pytest.raises(CryptoError):
        import_adapter.import_and_persist(payload, agent, tmp_path, store)


def test_a_non_dict_payload_is_rejected(tmp_path):
    agent, _ = _agent(tmp_path)
    store = TeamSyncStore(tmp_path / "team_sync")

    with pytest.raises(ProtocolError):
        import_adapter.import_and_persist("not-a-dict", agent, tmp_path, store)
