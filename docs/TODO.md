# TODO — Police Agent

## Step 1 — Project setup (done)

- [x] `uv init`, `pyproject.toml` deps (fastmcp, pytest, pytest-cov, ruff)
- [x] Ruff / pytest / coverage config (85% fail-under)
- [x] `src/police_agent/{domain,infra,peer,shared}` package skeleton
- [x] `config/police/` with shared `game.json` and private `game.toml.example`
- [x] Smoke test, `.gitignore`, README/PLAN/TODO/PRD

## Step 2 — Core game/domain rules (done)

- [x] `constants.py`: `Role`, `MoveType`, `Direction` (N/S/E/W only), `DELTAS`
- [x] `domain/board.py`: bounds, orthogonal steps, `legal_moves`,
      `barrier_targets` (own cell + 4 neighbours, per spec 3.4)
- [x] `domain/actions.py`: validated `Action` value object
- [x] `domain/own_state.py`: position, visited, barrier quota, `is_confined`
- [x] `domain/rules.py`: step ceiling, survival-threshold check
- [x] `domain/scoring.py`: scoring table + series tie rule
- [x] Split into a police-only repository (spec ch. 2.4.2, 9.4)

## Step 4 — P2P/FastMCP communication (done, built out of order)

- [x] `peer/protocol.py`: `TurnMessage` / `AuditPayload` / `ControlMessage`;
      `from_dict` rejects missing required fields, tolerates unknown ones so a
      another team's superset stays interoperable (ch. 9.4)
- [x] `infra/mcp_server.py`: this peer's own server — `PeerInboxes`,
      `build_peer_server`, `start_peer_server`, port-conflict guard
- [x] `infra/mcp_client.py`: `McpTransport` — retrying outbound calls, inbox
      polling, `drain_inboxes` for a restarted sub-game
- [x] Two-port integration test over real HTTP sockets (`@pytest.mark.slow`)
- [ ] Not done here: the runtime loop that drives the transport (step 8), and
      the config loader that supplies `my_port` / `opponent_url` — timeouts and
      URLs are constructor arguments for now

## Step 6 — Scent and belief (done)

- [x] `domain/scent.py`: `ScentField` — the mandatory pheromone mechanism, to
      ch. 4.3's update law `τ(t+1) = (1−ρ)·τ(t) + Δτ` clamped at zero. Radial
      deposit over the agreed 5×5 window, multiplicative decay once per full
      turn, `{"r,c": intensity}` snapshot. Constants come from the signed terms
      (Appendix ו table 16 marks all three *kavua*); nothing here invents one.
      Tests pin it against figure 4, figure 5 and ch. 4.4's worked example
- [x] `strategy/belief.py`: `BeliefGrid` — the Bayesian belief map of ch. 6.4.
      Flat prior, `diffuse()` predict over the agreed orthogonal move set,
      `observe_smell()` update by `1 + trust·τ`, normalise, `exclude()`,
      `as_matrix()` for the step-8 heatmap. Pairs with the existing Manhattan
      chase to give the "Bayes + Manhattan" policy the book recommends (6.3.1)
- [x] `strategy/threat.py`: `ThreatEstimate` widened to the three calls the turn
      loop makes; `absorb()` was being called without ever being declared
- [x] Wired: `peer/turn_handler.py` diffuses *then* observes (predict before
      update), `peer/runtime.py` builds both from the terms, `NullScent` and
      `strategy/scent_threat.py` retired
- [ ] `belief.smell_trust` (default 4.0) is untuned — it is the one knob that
      decides how fast a reading overwhelms the prior. Tune it against a live
      thief, not against the fake transport
- [ ] The absorbed opponent trail is not kept: the belief consumes each received
      grid directly. `ScentField.absorb`/`decay_all`/`strongest_cell` exist and
      are tested for when the step-8 GUI wants a trail layer to draw

## Step 7 — Police strategy (done, built out of order)

- [x] `strategy/brain.py`: `PoliceBrainBase` seam + shipped `PoliceBrain`
      (minimise Manhattan distance, tie-break toward unvisited)
- [x] `strategy/barrier.py`: deterministic placement — wall only when it leaves
      the believed thief ≤ 1 escape, never when it would confine the police (3.4)
- [x] `strategy/threat.py`: `ThreatEstimate` Protocol + `PointThreat` /
      `UniformThreat` stand-ins until the belief map lands
- [x] `strategy/__init__.py`: `resolve_brain` reading `strategy.police_class`
- [ ] Re-tune once step 6 supplies a real `BeliefGrid` — the stand-in estimates
      are certain in a way a real belief never is, which flatters the heuristic

## Step 3 / 8 — Runtime peer process (done, built out of order)

- [x] `shared/config.py` + `shared/schema.py`: load the agreed `game.json` and
      the private `game.toml`, dotted access. The agreed file is overlaid *on
      top of* the private one so a peer cannot sign one board and play another
- [x] `peer/terms.py`: the must-match subset, validated before a port is opened
- [x] `peer/handshake.py`: mutual signed-terms exchange (`Negotiation`)
- [x] `peer/runtime.py`: `PoliceRuntime` — negotiate → wait → fold in → decide
      and send → audit. The thief opens, so the police waits first
- [x] `peer/turn_handler.py` / `peer/turn_sender.py` / `peer/sealing.py`
- [x] `peer/summary.py`: audit exchange; a forged opponent log forfeits
- [x] `domain/crypto.py`: SHA-256 commit-reveal (partial step 5 — see below)
- [x] `__main__.py`: `police-agent` CLI (`--port`, `--opponent`, `--summary`)
- [x] `tests/peer/fake_transport.py`: scripted thief double, same six-method
      surface as `McpTransport`; plus a live two-port match in `tests/infra/`

## Step 3 — Local playable simulation (superseded)

Overtaken by the runtime above: the scripted match driver this step called for
is `tests/peer/fake_transport.py`, and it drives the real `PoliceRuntime`
rather than a separate simulation path.

- [ ] Load `config/police/game.json` into the domain layer
- [ ] Test double standing in for the thief (test scaffolding only — never
      shipped agent code, and never an in-process opponent at runtime)
- [ ] Scripted match driver; random/scripted move choice only, since real
      strategy is step 7

## Carried forward

- [ ] **Cross-repo — the thief does not concede a barrier capture.** When a
      police barrier traps the thief (Appendix ה 46/47), the thief's runtime
      sets its own result to `capture` but sends its terminal message with
      `claim_response = None`. The police only registers a win on
      `claim_response.caught`, so it keeps playing, times out, and records
      `technical_loss`. Both peers name the police as winner, but the two
      `result` strings disagree. Fix belongs in the **thief repo** (send
      `{"caught": true}` on that path); settle it before the league match.
- [ ] **Cross-repo — timeout asymmetry.** The thief waits 30 s for the audit
      reveal; this peer's turn timeout falls back to 60 s, and to **180 s** if
      `game.toml` is copied unchanged from the example. The thief will walk away
      before the police notices it has gone. Agree one number.
- [ ] **Cross-repo — the scent model must be locked before the series.** Appendix
      ה 23 makes this a condition of the game being valid at all ("deviation in
      the decay formula voids the game"), and ch. 4.5 asks the two groups to
      agree the emission/decay model in full and hash it. `domain/scent.py`
      follows the **book**, and reproduces all four of its published numbers
      (figure 4's window, figure 5's curve, ch. 4.4's `0.81`, and the stated
      `[0, 0.9]` range). The course **reference implementation does not**, in
      three places — so an opponent who copied it will compute a different
      field, and this is the conversation to have before the league:
      | | Ours (the book) | Reference |
      |---|---|---|
      | Decay | `(1−ρ)·v`, still ≈0.11 at t=20 | `v − 0.10`, gone by t=9 |
      | Falloff | radial 0.90/0.62/0.42/0.20/0.14/0.04 | Chebyshev rings 0.9/0.6/0.3 |
      | Order | decay then deposit → centre goes out at `0.9` | deposit then decay → `0.8` |
      The three *values* (0.9, 0.10, 5×5) are Appendix ו table 16 fixed
      constants and are identical either way; only the formulas differ.
- [ ] **Two readings the book does not settle**, both decided in `domain/scent.py`
      and worth putting in the agreement explicitly rather than leaving implicit:
      the falloff *curve* (a Gaussian at σ=1.15 is what reproduces figure 4, but
      ch. 4.5 leaves the curve to the two groups), and whether `+ Δτ` means
      accumulate or refresh (we refresh — ch. 4.4's `0.81` only holds that way,
      and it is what makes the stated `[0, 0.9]` range hold without a clamp).
- [ ] **Cross-repo — the thief still hardcodes `smell_grid={}`.** This peer now
      broadcasts a real decaying field, so the police's belief map is fed, but
      the thief's is not and it must fall back on its prior. Until that side
      emits too, a match is still not a symmetric test of strategy. Fix belongs
      in the **thief repo**.
- [ ] **Step 5 is only half done.** Sealing, the handshake signature and the
      hash re-verification of the opponent's revealed log all work. What is
      still missing is the *semantic* audit: re-checking the thief's capture
      answers and survival claim against its revealed positions. `audit_records`
      proves the log was not rewritten; it does not yet prove the log is
      consistent with what the thief claimed during play.
- [ ] **No nonce anti-replay** on incoming turns — a replayed message would be
      processed twice. Track seen `(step, commit)` pairs.
- [ ] **Specification ambiguity — Appendix ה 46.** The barrier policy never
      walls the cell it *believes* the thief occupies, even though a barrier
      there is a capture condition: the specification does not pin down how that
      is evaluated against a sealed, simultaneous move. Stepping onto the cell is
      a capture attempt that costs no quota, so the ambiguous option is never the
      only one available. Resolve the timing with the other group before the
      interoperability test, then revisit `strategy/barrier.py`.
- [ ] **`_send_with_retry` catches bare `Exception`** — a genuine bug such as a
      misspelled tool name retries for the full connect budget before surfacing
      as a `TransportError`. Narrow it once the runtime loop exercises the path.

- [ ] **Step 5 — audit verification.** The thief-side capture rules (Appendix ה
      46/47) were removed from `domain/rules.py` because the police cannot
      compute them during play. The police still owes their *verification*:
      once the thief reveals its sealed log, re-check every capture-claim
      answer, every barrier-capture report and any confinement claim against
      the revealed positions. Operates on the opponent's revealed records, not
      on `OwnGameState`.
- [x] Companion **thief repository** created and cross-linked from `README.md`:
      https://github.com/Moaawiyah/Ai_thief (public, so accessible to the grader).
- [ ] Add the reverse cross-link in the **thief repo's** README, pointing back to
      https://github.com/Moaawiyah/police-agent — ch. 9.4 requires the link in
      *both* directions. Done in that repo, not this one.
- [ ] Merge the feature branch into the main branch (Appendix ג).
