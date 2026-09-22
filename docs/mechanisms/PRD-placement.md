# Mechanism PRD — Barrier Candidate Scoring

Required by the structure guideline (§17.1): a dedicated PRD per central
algorithm. Scope here is `strategy/placement.py` only.

This is a companion to `PRD-barrier-strategy.md`, not a replacement for it:
that PRD owns *whether* a wall is legal and worth making at all (the safety
rules and the accept/reject bar); this one owns *which* legal candidate wins
once more than one clears that bar. `strategy/barrier.py` calls
`placement.py::best_placement` for that ranking — the PRD-barrier-strategy.md
source column citing `barrier.py::_best_placement` predates the split into
this module and should be read as `placement.py::best_placement`.

## 1. Problem

On any turn the police has at most five legal placements: the cell underfoot
and its four neighbours (spec 3.4). More than one can clear the
accept/reject bar from `PRD-barrier-strategy.md` (an escape removed, or
enough pocket area shrunk). Picking the first one that qualifies, in board
enumeration order, ignores that a belief is a distribution, not a point: a
candidate next to more of the probability mass is a better bet than one next
to only the argmax cell, even when both qualify equally on the argmax alone.

## 2. Users

- **`strategy/barrier.py::choose_barrier`** — calls `best_placement` once it
  has decided walling is worth considering this turn at all; the ranking
  never runs unless the legality/benefit bar has already been checked.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| P1 | Score a candidate as the sum of an escape term and an area term, evaluated across the top-K belief cells (weighted by probability) rather than the argmax alone. | `strategy/placement.py::_score` |
| P2 | The escape term fires only when the candidate is adjacent (board distance 1) to a weighed cell; the area term is the drop in that cell's flood-fill reachable area the candidate would cause. | `strategy/placement.py::_score`, `_area_gain` |
| P3 | Belief weights are renormalised over the top-K slice before scoring (a top-K slice does not sum to one); an empty/zero-weight slice falls back to full weight on the primary believed cell. | `strategy/placement.py::_normalised` |
| P4 | A candidate earns nothing from belief mass sitting on its own cell — a walled cell cannot simultaneously be where the thief is believed to stand. | `strategy/placement.py::_score`, `tests/strategy/test_placement.py::TestBeliefWeights` |
| P5 | Ties in score fall back to board enumeration order (N, E, S, W from the candidate generator), so two candidates that score identically resolve the same way every replay. | `strategy/placement.py::best_placement`, `tests/strategy/test_placement.py::TestRankingBeatsBoardOrder` |
| P6 | The legality/safety filtering (never the cell underfoot or the believed cell, never self-imprisoning, never lengthening the path except on the last escape) runs before scoring — see `PRD-barrier-strategy.md` R2–R4 for those rules; this module does not re-derive them, it consumes their outcome. | `strategy/placement.py::best_placement` |

## 4. Non-functional requirements

- **Deterministic ranking.** Scoring is exact arithmetic over a fixed
  candidate order and a fixed belief snapshot — no randomness — so a
  placement stays recomputable from replayed state at the end-of-game audit,
  the same guarantee `PRD-barrier-strategy.md` states for the decision as a
  whole.
- **Measured constants, not assumed ones.** `TOP_K = 3` and
  `ESCAPE_WEIGHT = 0.5` were both set by sweeping the parameter against an
  adversarial, flee-on-sight thief over 360 starting positions. Capture rate
  peaks sharply at K=3 (0.6% at K=1, 1.4% at K=2, 2.8% at K=3, then 1.9% at
  K=4, 0.6% at K=8 as the tail drowns the head); `ESCAPE_WEIGHT` below 1.0
  outperforms every tested value at or above it (2.8% at 0.5 vs. 1.7% at
  weights ≥1, 0.3% at 64) because over-weighting the escape term collapses
  the ranking onto whichever cell the thief could step to next and ignores
  what a wall does to the rest of its ground.

## 5. Explicit non-goals

- Deciding whether to wall at all — that is `strategy/barrier.py` and
  `PRD-barrier-strategy.md`.
- Multi-turn lookahead over candidate walls — every score is computed
  against the current belief snapshot only, same as the parent PRD.

## 6. Success criteria

`tests/strategy/test_placement.py` pins the ranking against board order
(`TestRankingBeatsBoardOrder`), confirms both score terms can independently
decide a placement (`TestBothScoreTerms`), and confirms the safety rules stay
absolute regardless of score (`TestSafetyRulesAreAbsolute`). Combined with
`PRD-barrier-strategy.md`'s benchmark, the scored ranking is part of what
gets that PRD's ≥85% capture rate at well under half the barrier quota spent.
