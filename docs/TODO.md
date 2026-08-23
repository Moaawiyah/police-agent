# Police Agent — current work and release gaps

This file tracks actionable gaps on the current `master`. Historical implementation notes
belong in Git history and the feature documentation, not in this checklist.

## Completed and verified

- [x] Separate Police and Thief repositories and processes.
- [x] Shared `game.json` contract, locally byte-identical, with a signed negotiation subset.
- [x] FastMCP negotiation, turn, control and audit tools.
- [x] Queue-based inbound orchestration, outbound gatekeeping and loop watchdog.
- [x] Legal movement, scent field, Bayesian belief update and hint reliability.
- [x] Explainable chase and deterministic barrier selection; seeded random tie-breaks.
- [x] Commit-reveal, anti-replay, step-zero declaration and semantic audit.
- [x] Two-game series driver and four mandatory JSON artifact types.
- [x] Live GUI, production-log replay, dual-agent display and GIF/MP4 export path.
- [x] Gmail send-only implementation, local draft flow and setup guide.
- [x] Fresh localhost two-process series on 2026-08-12: Police 2–0, score 40–10.
- [x] Fresh cross-log replay: both production logs re-verified, `Verified OK` displayed.
- [x] Current quality gate: 1,242 passed, 0 skipped, 95.37% coverage over `src/` + `research/`
  (93% with no omissions), Ruff clean, formatting clean and all Python files within the
  150-line cap.
- [x] MIT licence, ISO/IEC 25010 mapping and documented extension points added.
- [x] Parameter sensitivity study: nine constants swept at 500 episodes/point with 95%
  intervals, figures and a notebook ([RESEARCH.md](RESEARCH.md)).

## Required before claiming submission readiness

- [x] Final-result consensus mismatch resolved in `a613b6f`: `roles_of()` returned
  `{role: group}` while the sibling thief repo and najamjad's independent implementation
  both use `{group: role}`, and `agreement_core` hashes that block verbatim. Verified
  against a real exchanged report -- all three now agree byte-for-byte on
  `mutual_agreement.sha256` and `interop_sha256`.
- [ ] Run the current revisions through authenticated ngrok reserved domains on separate
  public endpoints; record both peer revisions, URLs, results, audits and released ports.
- [ ] Complete and preserve valid matches against at least two different external opponent
  groups, as required by the project league evidence.
- [ ] Exercise Gmail OAuth with the `gmail.send` scope and perform one deliberate real send
  of the aggregate JSON attachment. Never commit credentials or tokens.
- [ ] Re-run replay from the final league logs and capture the live GUI plus exact
  `Verified OK` status.
- [ ] Confirm both repositories cross-link the final published branches and revisions.
- [ ] Create the annotated `v1.0-submission` tag only after every item above passes.

## Useful improvements that do not block local play

- [ ] Add a replay sub-game selector instead of requiring a per-game filename.
- [ ] Show the public tunnel URL inside the GUI when `--tunnel --gui` is used.
- [ ] Persist Police's outgoing verbal reply in the production log for complete replay text.
- [ ] Narrow the broad retry exception in `McpTransport._send_with_retry` to expected
  transport failures.
- [ ] Make the tunnel a pluggable seam. `sdk/agent_connection.py:75` calls ngrok directly and
  `sdk/league.py:13` hard-requires `--tunnel` plus `network.tunnel_domain`, so an externally
  managed tunnel cannot use `--league` and silently loses the public-opponent-URL check and
  the `turn_timeout_seconds == watchdog_timeout_seconds` guard. A `network.public_url` key
  that league mode validates instead would close it.

## Evidence discipline

Raw logs, private config and OAuth files remain local and ignored. Commit only redacted,
reviewed evidence such as the two screenshots under `assets/`. Record the exact commit IDs
for every future live run; passing unit tests or matching tool names alone are not
interoperability proof.
