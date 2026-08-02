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
- [x] `strategy/scent_threat.py`: interim argmax-of-scent threat estimate
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
- [ ] **Scent emission is a no-op** (`peer/seams.py`, `NullScent`). Note the
      thief's `turn_message` also hardcodes `smell_grid={}`, so *both* sides are
      currently blind and the belief systems on both sides get no input. The police
      broadcasts an empty `smell_grid`, so an opponent gets no signal from us
      and must fall back on its prior. A match runs correctly end to end and is
      worth running to prove the wiring, but it is **not a fair test of either
      strategy** until step 6 supplies a real decaying field.
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
