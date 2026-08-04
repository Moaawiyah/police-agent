"""Naming the commit that played: honest, or honestly "unknown".

Rule 53 exists so the grader can check out the exact revision that competed.
The failure modes therefore matter more than the happy path: every one of them
must degrade to "unknown" rather than cost the match, and none of them may
report a hash that would not resolve on GitHub.
"""

import pytest

from police_agent.infra import gitcommit
from police_agent.infra.gitcommit import UNKNOWN, commit_hash, working_tree_dirty
from tests.conftest import config_with
from tests.infra.fake_commands import MISSING, TIMEOUT, FakeCommands

SHA = "9f1c2b7a4d3e5f60718293a4b5c6d7e8f9012345"


@pytest.fixture(autouse=True)
def _fresh_cache():
    gitcommit._probed_hash.cache_clear()
    working_tree_dirty.cache_clear()
    yield
    gitcommit._probed_hash.cache_clear()
    working_tree_dirty.cache_clear()


def probe(monkeypatch, replies=None) -> FakeCommands:
    return FakeCommands(monkeypatch, gitcommit, replies)


class TestTheHappyPath:
    def test_a_clean_checkout_reports_its_head(self, monkeypatch):
        probe(monkeypatch, {"rev-parse": SHA})

        assert commit_hash() == SHA

    def test_it_asks_for_head_so_a_detached_checkout_still_answers(self, monkeypatch):
        """A branch name would come back empty with HEAD detached."""
        fake = probe(monkeypatch, {"rev-parse": SHA})
        commit_hash()

        assert fake.calls[0][3:] == ["rev-parse", "HEAD"]

    def test_the_commit_is_read_once_and_then_remembered(self, monkeypatch):
        fake = probe(monkeypatch, {"rev-parse": SHA})
        commit_hash()
        commit_hash()

        assert len(fake.calls) == 1


class TestADirtyTree:
    def test_uncommitted_work_is_reported_alongside_the_hash(self, monkeypatch):
        probe(monkeypatch, {"rev-parse": SHA, "status": " M src/police_agent/peer/runtime.py"})

        assert working_tree_dirty() is True

    def test_the_hash_stays_resolvable_rather_than_gaining_a_dirty_suffix(self, monkeypatch):
        """The grader has to `git checkout` this value; `<sha>-dirty` would not."""
        probe(monkeypatch, {"rev-parse": SHA, "status": " M anything"})

        assert commit_hash() == SHA

    def test_a_clean_tree_says_so(self, monkeypatch):
        probe(monkeypatch, {"rev-parse": SHA, "status": ""})

        assert working_tree_dirty() is False


class TestWhenGitCannotAnswer:
    @pytest.mark.parametrize(
        "replies, why",
        [
            ({}, "not a repository, or a repository with no commits (rc 128)"),
            ({"rev-parse": MISSING}, "git is not installed"),
            ({"rev-parse": TIMEOUT}, "git hung past the timeout"),
        ],
    )
    def test_an_unanswerable_question_is_unknown_and_never_an_exception(
        self, monkeypatch, replies, why
    ):
        probe(monkeypatch, replies)

        assert commit_hash() == UNKNOWN, why

    def test_a_broken_probe_does_not_make_the_tree_look_dirty(self, monkeypatch):
        probe(monkeypatch, {"status": MISSING})

        assert working_tree_dirty() is False


class TestTheConfiguredOverride:
    def test_a_declared_commit_wins_over_the_probe(self, monkeypatch):
        """The escape hatch for running from a build artefact with no .git."""
        probe(monkeypatch, {"rev-parse": SHA})
        declared = config_with(game__github_commit="abc123")

        assert commit_hash(declared) == "abc123"

    def test_an_empty_declaration_falls_back_to_the_probe(self, monkeypatch):
        probe(monkeypatch, {"rev-parse": SHA})

        assert commit_hash(config_with(game__github_commit="")) == SHA

    def test_no_config_at_all_is_allowed(self, monkeypatch):
        probe(monkeypatch, {"rev-parse": SHA})

        assert commit_hash(None) == SHA


def test_the_probe_never_reaches_the_network(monkeypatch):
    """`fetch`/`ls-remote` would block on a bad connection and stall the match."""
    fake = probe(monkeypatch, {"rev-parse": SHA, "status": ""})
    commit_hash()
    working_tree_dirty()

    assert all(call[3] in ("rev-parse", "status") for call in fake.calls)
