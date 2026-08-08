# Mechanism PRD — Pheromone Scent + Bayesian Belief

Required by the structure guideline (§17.1): a dedicated PRD per central
algorithm, rather than folding every mechanism into the one project-level
`docs/PRD.md`. Scope here is `domain/scent.py`, `domain/scent_kernel.py`, and
`strategy/belief.py`.

## 1. Problem

The police never observes the thief's true cell (book ch. 2, rules 8/9). The
only physical evidence is a decaying pheromone trail each side emits by the
mere act of moving — unforgeable, but indirect. The police must turn that
trail into a usable estimate of where the thief is *now*, not where it was
several turns ago when the trail was fresher.

## 2. Users

- **`strategy/brain.py`** — consumes `ThreatEstimate.most_likely()` for both
  the chase target and the barrier-placement target.
- **The opposing thief peer** — receives this peer's own emitted field over
  the wire every turn (`smell_grid` in `TurnMessage`) and must be able to
  independently reproduce the same physics from the agreed constants.
- **The end-of-game report** — `belief_log` records one Bayes-filter update
  per turn (`peer/runtime_loop.py`) for the replay viewer and the audit.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| B1 | Emit a radial pheromone field on every move, centred at full intensity, falling off within the agreed grid size. | book ch. 4, `domain/scent_kernel.py` |
| B2 | Decay every held cell by the agreed rate each full turn; drop cells below a fixed trace floor rather than leaving a permanent stain. | Appendix Vav table 16, `domain/scent.py:_TRACE_FLOOR` |
| B3 | A cell's intensity is the max of all deposits landed there, never the sum — re-depositing refreshes a cell, it does not stack it. | `domain/scent.py::deposit` |
| B4 | Predict the thief's position before folding in new evidence: spread belief mass over legal one-step moves (or hold) before observing. | `strategy/belief.py::diffuse`, ch. 6.4 |
| B5 | Normalize each incoming scent reading against *its own* peak intensity, not an absolute value, before the nonlinear boost. | `strategy/belief.py::observe_smell` |
| B6 | Boost a cell's probability by `1 + smell_trust * reading**smell_power`; leak a small fraction of the posterior back toward uniform every observation so a stale hot cell cannot dominate forever. | `strategy/belief.py`, `DEFAULT_LEAK` |
| B7 | Malformed or out-of-bounds wire entries are skipped, never fatal — the opponent's implementation is untrusted input. | `strategy/belief.py::_parse` |
| B8 | The physical constants (centre intensity, decay rate, field size) are signed, agreed terms; the emission kernel's exact shape and the belief's trust/power/leak tuning are private, unsigned choices. | `peer/terms.py`, `game.toml.example` |

## 4. Non-functional requirements

- **Determinism.** `diffuse()`/`observe_smell()` are pure functions of the
  current grid and the incoming reading — no randomness, so a replay
  recomputes the identical posterior from a saved log.
- **Reproducing a moving target, not a stale trail.** Measured directly
  (`tests/strategy/test_belief_tracking.py`): the shipped filter keeps more
  mass near the thief's *current* cell and less on cells it visited several
  turns ago than a linear, no-leak filter would, across a continuous chase.
- **Tunable without breaking interop.** `smell_trust`/`smell_power`/`leak`
  are read from this peer's own private config; changing them cannot desync
  the handshake, because none of the three is a signed term.

## 5. Explicit non-goals

- Modelling the *opponent's* belief about this agent — each side's posterior
  is private and never exchanged.
- A continuous (non-grid) probability field — the board is discrete, so is
  the belief.
- Using the LLM anywhere in this pipeline — inference is pure Python
  arithmetic (CLAUDE.md: an LLM is never the authoritative engine).

## 6. Success criteria

Across a full match, `most_likely()` tracks a continuously-moving thief
closely enough that `strategy/brain.py`'s chase heuristic closes the gap every
turn it is not already walled off (`tests/strategy/test_brain.py`), and the
belief map rendered in the live GUI visibly follows the trail rather than
smearing into a comet tail behind it.
