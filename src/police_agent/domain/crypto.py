"""Commit-reveal: how two peers who cannot see each other stay honest.

Each turn a peer seals its true position, move and verdict under
`commit = SHA256(canonical_json(payload) | nonce)` and sends only the digest.
The nonce stays private until the end of the game, so the opponent learns
nothing from the commit -- but the peer can no longer change its mind about what
it did, because any other payload produces a different digest.

At the audit both sides reveal every nonce and re-run the hash over the revealed
payloads. That is the whole enforcement mechanism: there is no referee, so the
only thing preventing a peer from rewriting its history after seeing how the
game went is that the rewritten history would not hash to what it already sent.

This module is pure and has no I/O, which is why it sits in `domain/`: the same
code seals during play and re-verifies during the audit, and a test can check
one against the other without a network.
"""

import hashlib
import json
import secrets
from typing import Any

from police_agent.exceptions import CryptoError

NONCE_BYTES = 16


def canonical_json(payload: dict[str, Any]) -> str:
    """Key-order-independent JSON, so two peers hash the same bytes.

    Without sorted keys an honest peer could fail its own audit purely because
    its dict happened to be built in a different order.

    The separators are **compact** and that is load-bearing, not styling: this
    is the exact byte sequence every commitment is taken over, so a stray space
    would change every digest this repository has ever published. The report
    layer needs a second, *spacier* canonical form for the artifact signatures
    the opposing team computes -- see `report/ids.py`, which keeps the two apart
    and explains which field uses which. Public rather than private because that
    module has to reach it; it was always what the docstring above called it.
    """
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class CommitReveal:
    """Seal a payload, and later prove what was sealed."""

    @staticmethod
    def commit_of(payload: dict[str, Any], nonce: str) -> str:
        return hashlib.sha256(f"{canonical_json(payload)}|{nonce}".encode()).hexdigest()

    @classmethod
    def seal(cls, payload: dict[str, Any]) -> dict[str, str]:
        """A fresh nonce and the commitment it produces for `payload`.

        The nonce is what stops the commitment being brute-forced: the payload
        space is small enough (a position and a move on a 7x7 board) that an
        unsalted hash could simply be enumerated.
        """
        nonce = secrets.token_hex(NONCE_BYTES)
        return {"nonce": nonce, "commit": cls.commit_of(payload, nonce)}

    @classmethod
    def verify(cls, payload: dict[str, Any], nonce: str, commit: str) -> None:
        """Raise CryptoError unless `payload` and `nonce` hash to `commit`."""
        recomputed = cls.commit_of(payload, nonce)
        if recomputed != commit:
            raise CryptoError(
                f"Commit mismatch: published {commit[:16]}..., recomputed {recomputed[:16]}..."
            )


def audit_records(records: list[dict]) -> dict:
    """Re-verify a revealed log, reporting every step rather than the first failure.

    A single mismatch is enough to reject the log, but which steps failed is
    what makes the result explainable in the report, so all of them are
    collected. A record missing its nonce or commit fails like any other: an
    incomplete reveal proves nothing, and treating it as a pass would let a peer
    escape the audit simply by omitting the step it wants to hide.

    `peer_tokens_total` sums whatever `tokens` each revealed payload declares --
    0 for a peer whose payload schema omits the key (SPEC 3: not an interop
    constraint). It is summed here rather than trusted blindly: the caller only
    uses it when `passed` is true, since an unverified reveal proves nothing.
    """
    failed: list[int] = []
    tokens_total = 0
    for index, record in enumerate(records):
        payload = record.get("payload")
        if not isinstance(payload, dict):
            failed.append(index)
            continue
        try:
            CommitReveal.verify(payload, record.get("nonce", ""), record.get("commit", ""))
        except CryptoError:
            failed.append(payload.get("step", index))
        tokens_total += int(payload.get("tokens") or 0)
    return {
        "passed": not failed,
        "verified_steps": len(records) - len(failed),
        "failed_steps": failed,
        "peer_tokens_total": tokens_total,
    }
