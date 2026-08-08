# Mechanism PRD — Commit-Reveal and End-of-Game Audit

Required by the structure guideline (§17.1): a dedicated PRD per central
algorithm. Scope here is `domain/crypto.py`, `peer/sealing.py`,
`peer/step_zero.py`, and the audit path in `peer/summary.py`.

## 1. Problem

There is no referee and no central server (book ch. 2.4.2). Each peer is the
sole authority over its own true state, and the other side's client is
untrusted code from a different team. Without a cryptographic mechanism,
either side could rewrite its history after seeing the outcome — claim a
different position, a different move, a different capture verdict — and
nothing on the wire would contradict it.

## 2. Users

- **Both peers, symmetrically** — every turn is sealed by its own sender and
  independently re-verified by the receiver at the audit; the mechanism has
  no privileged side.
- **`report/*`** — the four mandatory artifacts embed each commit and, for
  the log artifact, the full sealed record set, so a lecturer can re-run the
  same verification offline.
- **The replay viewer** — re-derives `Verified OK` from the same records a
  live match produced, so a replay is not merely a visual playback but a
  second, independent audit pass.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| C1 | Seal every turn as `commit = SHA256(canonical_json(payload) \| nonce)` before sending anything; the wire message carries the digest only, never the payload or the nonce. | `domain/crypto.py`, book ch. 5 |
| C2 | `canonical_json` sorts keys and uses compact separators — the exact byte sequence every commitment is taken over — so two independently-built dicts with the same content hash identically. | `domain/crypto.py::canonical_json` |
| C3 | The nonce is 16 cryptographically-random bytes, generated fresh per commitment, and withheld until the final reveal — a small, five-move space would be crackable by pre-hashing every possibility without one. | `domain/crypto.py::NONCE_BYTES` |
| C4 | The very first sealed record is a step-zero declaration — identity, code revision, and intent — signed before either side has made a move, so the declaration itself is inside every later audit's chain. | `peer/step_zero.py` |
| C5 | At the end of a sub-game, both peers reveal every nonce and payload for the records they sealed; each side re-hashes the *opponent's* revealed records and compares against the digests that peer sent live. | `peer/summary.py::exchange_and_audit` |
| C6 | A mismatch between a recomputed hash and the commit announced at the time is proof of tampering — SHA-256 leaves no statistical doubt — and is scored as a technical loss, not treated as an ambiguous dispute. | book ch. 5, `domain/rules.py` |
| C7 | An opponent that goes silent during the reveal (never answers `submit_audit`) still yields a match result: the audit is marked skipped rather than the process hanging indefinitely. | `peer/summary.py` |

## 4. Non-functional requirements

- **Purity.** `domain/crypto.py` performs no I/O and reaches no network — the
  identical code path seals during play and re-verifies during audit, so a
  unit test checks one against the other with no socket involved.
- **Two canonical forms, kept apart deliberately.** The compact form above is
  what every commitment is taken over; `report/ids.py` uses a second,
  spacier canonical form for the artifact signatures the opposing team
  recomputes independently. Conflating the two would change every digest
  this repository has ever published.
- **Fail loud, fail specific.** A hash mismatch raises `CryptoError` naming
  what failed to verify, not a generic assertion — the audit's whole point is
  to be legible to a human deciding a disputed match.

## 5. Explicit non-goals

- Preventing an opponent from *lying in its verbal hint* — the spec allows
  that explicitly (ch. 4.4); commit-reveal only proves what move and position
  were actually sealed, never whether a taunt was truthful.
- A trusted third party or shared ledger of any kind — the entire mechanism
  is designed to need neither.

## 6. Success criteria

Every sub-game this peer completes produces an audit that is either
`Verified OK` on both sides or names the exact step and field that failed to
re-hash — never a silent pass on tampered data and never an unexplained
failure on honest data (`tests/domain/test_crypto.py`,
`tests/peer/test_replay_guard.py`).
