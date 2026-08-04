import pytest

import police_agent
from police_agent import domain, infra, peer, report, sdk, shared


def test_package_importable():
    assert police_agent is not None


def test_subpackages_importable():
    assert domain is not None
    assert infra is not None
    assert peer is not None
    assert report is not None
    assert sdk is not None
    assert shared is not None


def test_the_sdk_is_the_package_front_door():
    """`police_agent.PoliceAgentSDK` is the same object as `police_agent.sdk`'s,
    so a front end never has to know which module it lives in."""
    assert police_agent.PoliceAgentSDK is sdk.PoliceAgentSDK
    assert police_agent.MatchOptions is sdk.MatchOptions


def test_the_console_script_propagates_the_exit_code(monkeypatch):
    """A league harness reads the exit code to tell a lost match from a crashed
    agent, so the shim must not swallow what the CLI returned."""
    monkeypatch.setattr("police_agent.__main__.main", lambda argv=None: 3)

    with pytest.raises(SystemExit) as exit_info:
        police_agent.main()

    assert exit_info.value.code == 3


def test_an_unknown_attribute_still_fails_as_one():
    """The lazy re-export must not turn a typo into an import error raised from
    somewhere else in the tree."""
    with pytest.raises(AttributeError, match="no attribute 'nonexistent'"):
        _ = police_agent.nonexistent
