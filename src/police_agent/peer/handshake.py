"""The pre-game handshake: agree on terms, or refuse to play.

Each peer sends `SHA256(terms | nonce)` alongside the terms themselves and
checks that the opponent signed *the same terms*. The signature is not there to
prove identity -- there is no key exchange and no certificate authority, so it
could not. It is there so that a peer which later disputes the rules cannot
claim it agreed to something else: the nonce it chose is bound to the terms it
sent.

Identity (group name, repositories) travels alongside but is deliberately *not*
signed. It legitimately differs between the two groups, so making it a
must-match term would mean no two groups could ever complete a handshake.
"""

import secrets

from police_agent.domain.crypto import NONCE_BYTES, CommitReveal
from police_agent.exceptions import CryptoError, ProtocolError
from police_agent.infra.gitcommit import commit_hash
from police_agent.infra.hardware import hardware_spec
from police_agent.shared.version import CODE_VERSION


class Negotiation:
    """One peer's side of the agreement exchange."""

    def __init__(self, terms: dict, identity: dict | None = None) -> None:
        self.terms = terms
        self.identity = identity or {}
        self.peer_identity: dict = {}
        self._nonce = secrets.token_hex(NONCE_BYTES)

    def signed(self) -> dict:
        """My agreement message: the terms, my nonce, and my signature over both."""
        return {
            "terms": self.terms,
            "nonce": self._nonce,
            "signature": CommitReveal.commit_of(self.terms, self._nonce),
            "identity": self.identity,
        }

    def verify_peer(self, message: dict) -> None:
        """Accept the opponent's agreement, or raise rather than start a bad game.

        Two distinct failures, kept distinct because they mean different things
        to whoever is debugging: a *mismatch* is a configuration problem the two
        groups can fix by comparing files, while a *bad signature* means the
        message was not produced by the peer that claims to have sent it.
        """
        for field in ("terms", "nonce", "signature"):
            if field not in message:
                raise ProtocolError(f"Agreement message is missing {field!r}")
        if message["terms"] != self.terms:
            raise CryptoError(
                f"Agreement terms mismatch:\n  mine:   {self.terms}\n  theirs: {message['terms']}"
            )
        CommitReveal.verify(message["terms"], message["nonce"], message["signature"])
        self.peer_identity = message.get("identity", {})


def identity_from_config(config, step_zero_commit: str | None = None) -> dict:
    """This peer's public identity, exchanged so each side can name the other.

    Per-group rather than per-role: the specification alternates roles across a
    series, so the group is the stable thing to identify.

    It carries the declaration fields too -- hardware, model, code version,
    commit -- because the pre-game declaration artifact has to describe *both*
    groups (ch. 9.3.3) and this exchange is the only moment either peer learns
    anything about the other. `step_zero_commit` is the digest of the sealed
    declaration: publishing it here, before the first move, is what stops the
    payload revealed at the audit from being a later invention.

    Safe to grow, unlike `peer/terms.py`. Identity is explicitly never compared
    (see `verify_peer`), so an added key cannot fail a handshake; an added
    *term* would fail every one against a peer that did not add it too.
    """
    return {
        "group_id": config.get("game.group_id", "unknown-group"),
        "group_name": config.get("game.group_name", "unnamed"),
        "members": config.get("game.members", []),
        "repos": config.get("game.repos", {}),
        "mcp_servers": config.get("game.mcp_servers", {}),
        "llm_model": config.get("llm.model", "none"),
        "code_version": CODE_VERSION,
        "hardware_spec": hardware_spec(),
        "github_commit": commit_hash(config),
        "step_zero_commit": step_zero_commit or "",
    }


def negotiate(terms: dict, identity: dict, transport) -> dict:
    """Exchange signed terms with the opponent and return its identity.

    Both peers send before either reads, so neither waits for a message the
    other is not going to send until it has heard from them first.
    """
    negotiation = Negotiation(terms, identity)
    peer_message = transport.exchange_agreement(negotiation.signed())
    negotiation.verify_peer(peer_message)
    return negotiation.peer_identity
