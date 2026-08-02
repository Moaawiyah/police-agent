"""The handshake: agree, or refuse to start."""

import pytest

from police_agent.exceptions import ConfigError, CryptoError, ProtocolError
from police_agent.peer.handshake import Negotiation, identity_from_config, negotiate
from police_agent.peer.terms import terms_from_config, validate_agreement
from tests.conftest import config_with
from tests.peer.fake_transport import FakeTransport

TERMS = {"board_size": 7, "max_steps": 35}


def test_a_peer_signs_the_terms_it_sends():
    message = Negotiation(TERMS).signed()

    Negotiation(TERMS).verify_peer(message)  # a peer holding the same terms accepts it


def test_different_terms_are_refused_even_with_a_valid_signature():
    """The opponent signed honestly -- but signed a different game."""
    theirs = Negotiation({**TERMS, "board_size": 9}).signed()

    with pytest.raises(CryptoError, match="terms mismatch"):
        Negotiation(TERMS).verify_peer(theirs)


def test_a_signature_that_does_not_cover_the_terms_is_refused():
    tampered = Negotiation(TERMS).signed()
    tampered["signature"] = "0" * 64

    with pytest.raises(CryptoError, match="Commit mismatch"):
        Negotiation(TERMS).verify_peer(tampered)


def test_a_truncated_agreement_message_is_a_protocol_error():
    with pytest.raises(ProtocolError, match="nonce"):
        Negotiation(TERMS).verify_peer({"terms": TERMS, "signature": "x"})


def test_identity_travels_but_is_not_a_must_match_term():
    """Two groups always differ here, so signing it would prevent every handshake."""
    theirs = Negotiation(TERMS, {"group_id": "them"}).signed()
    mine = Negotiation(TERMS, {"group_id": "me"})

    mine.verify_peer(theirs)

    assert mine.peer_identity == {"group_id": "them"}


def test_negotiate_returns_the_opponent_identity():
    transport = FakeTransport()

    peer = negotiate(TERMS, {"group_id": "me"}, transport)

    assert transport.agreement_sent["terms"] == TERMS
    assert peer == {"group_id": "me"}  # the fake echoes our own message back


def test_terms_normalise_start_cells_to_lists():
    """A tuple would sign differently from the list that arrives as JSON."""
    terms = terms_from_config(config_with(positions__cop_start=(1, 2)))

    assert terms["cop_start"] == [1, 2]


def test_validate_reports_every_missing_term_at_once():
    broken = config_with(board__size=None, rules__barriers_max=None)

    with pytest.raises(ConfigError) as caught:
        validate_agreement(broken)

    assert "board_size" in str(caught.value)
    assert "barriers_max" in str(caught.value)


def test_the_shipped_config_satisfies_the_agreement(config):
    terms = validate_agreement(config)

    assert terms["board_size"] == 7
    assert terms["cop_start"] == [0, 0]


def test_identity_falls_back_when_the_private_config_is_absent(config):
    assert identity_from_config(config)["group_id"] == "unknown-group"
