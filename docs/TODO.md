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

## Step 3 — Local playable simulation (next)

- [ ] Load `config/police/game.json` into the domain layer
- [ ] Test double standing in for the thief (test scaffolding only — never
      shipped agent code, and never an in-process opponent at runtime)
- [ ] Scripted match driver; random/scripted move choice only, since real
      strategy is step 7

## Carried forward

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
