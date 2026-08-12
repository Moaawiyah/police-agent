# Commit-reveal security and semantic audit

## Threat model

The opponent is independent and untrusted. During play, each side may claim a
move, capture response, or terminal outcome, but neither side should be able to
rewrite its hidden history after learning the result. The protocol therefore
publishes a commitment during play and withholds the nonce until the audit.

## Commit-reveal flow

For each accepted turn the Police seals a canonical payload containing the
private state needed for replay, the move, the relevant claim/verdict, and a
fresh nonce. The public turn carries only the digest. At audit time the peer
receives the payload, nonce, and original commit, recomputes the digest, and
reports every failure rather than stopping at the first one.

The Police commitment is implemented by
[`domain/crypto.py`](../src/police_agent/domain/crypto.py). Its canonical bytes
are part of the native wire contract shared with the companion Thief; changing
serialization is a protocol change, even if the decoded fields look identical.

## Step-zero declaration

Before the first move, the runtime seals a declaration containing the code
version/commit, group and sub-game identity, and best-effort hardware facts.
Its digest is exchanged during negotiation and its nonce is revealed only in
the audit. Unknown hardware values remain explicitly `"unknown"`; the probe
does not invent measurements.

Implementation: [`peer/step_zero.py`](../src/police_agent/peer/step_zero.py),
[`infra/hardware.py`](../src/police_agent/infra/hardware.py), and
[`infra/gitcommit.py`](../src/police_agent/infra/gitcommit.py).

## Anti-replay and semantic replay

Incoming commits are remembered before they affect state, so a repeated turn
does not get applied twice. Hash verification proves that a record was not
rewritten; semantic replay additionally checks chronological movement, legal
barriers, capture claims, claim responses, confinement, terminal messages, and
the reported outcome against the revealed positions and public barriers.

The public entry point is
[`domain/semantic_audit.py`](../src/police_agent/domain/semantic_audit.py),
with the chronological logic split across `semantic_records.py`,
`semantic_moves.py`, and `semantic_replay.py`. A failed audit is a match-level
technical outcome, not merely a warning to ignore.

## Privacy boundary

Live `TurnMessage` objects contain scent and hints but not the opponent's true
position or move. The opponent's true path becomes available only in a
revealed audit log or an explicitly supplied replay input. The GUI follows the
same boundary: live view shows a belief heatmap; replay may show revealed
positions.

## Evidence and tests

- Cryptographic tests: [`tests/domain/test_crypto.py`](../tests/domain/test_crypto.py)
  and [`tests/peer/test_replay_guard.py`](../tests/peer/test_replay_guard.py).
- Semantic audit tests: `tests/domain/test_semantic_audit*.py` and
  `tests/peer/test_reporting_gates.py`.
- Transport and contract tests: [`tests/peer/`](../tests/peer/) and
  [`tests/infra/`](../tests/infra/).

## Open boundaries

Commit-reveal does not create identity or a public-key signature authority;
the course-compatible signature field is a hash and the non-retroactive
property comes from the withheld nonce. Cross-repository claims still require
the opponent to reveal a compatible record, and a Police-as-cop audit does not
prove that this repository can run the thief role.
