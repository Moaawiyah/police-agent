import police_agent
from police_agent import domain, infra, peer, shared


def test_package_importable():
    assert police_agent is not None


def test_subpackages_importable():
    assert domain is not None
    assert infra is not None
    assert peer is not None
    assert shared is not None
