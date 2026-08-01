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

## Step 3 — Local playable simulation (next)

- [ ] Load `config/police/game.json` into the domain layer
- [ ] Test double standing in for the thief (test scaffolding only — never
      shipped agent code, and never an in-process opponent at runtime)
- [ ] Scripted match driver; random/scripted move choice only, since real
      strategy is step 7

## Carried forward

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
