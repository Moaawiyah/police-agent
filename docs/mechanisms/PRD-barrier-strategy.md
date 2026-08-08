# Mechanism PRD — Barrier Placement Strategy

Required by the structure guideline (§17.1): a dedicated PRD per central
algorithm. Scope here is `strategy/barrier.py` and `strategy/encirclement.py`.

## 1. Problem

A barrier is a scarce, irreversible resource: a fixed quota for the whole
sub-game, and placing one costs the turn's movement (spec 3.4). A greedy
policy that walls whenever legally possible can hand the thief a wider
corridor, trap the police itself behind its own wall, or simply waste a turn
against a thief that is still free to flee — all three are measured failure
modes of naive designs, not hypothetical ones (see §4).

## 2. Users

- **`strategy/brain.py`** — calls `choose_barrier` every turn before falling
  back to `_pick_move`; a returned `Decision` pre-empts movement entirely.
- **`peer/turn_sender.py`** — supplies `rounds_left` (`max_steps -
  step_number`) so the policy can tell a mid-match turn from an endgame one.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| R1 | Within `BARRIER_REACH` (2 cells — the geometric maximum at which any wall can touch one of the believed cell's immediate escapes), remove a genuine escape when reachable. | `strategy/barrier.py::_best_placement` |
| R2 | Never wall the cell underfoot, and never wall the believed cell itself (a barrier there is an ambiguous capture condition the spec does not resolve against a sealed, simultaneous move). | `strategy/barrier.py::choose_barrier` |
| R3 | Never place a wall that would leave the police with no legal step of its own. | `strategy/barrier.py::_would_confine` |
| R4 | Unless it is the thief's *last* remaining escape (sealing it is the capture), a close-range wall must not lengthen the police's own barrier-aware path to the believed cell. | `strategy/barrier.py::_best_placement` |
| R5 | Past `BARRIER_REACH`, out to `WIDE_REACH` (4), judge a wall by how much it shrinks the believed cell's whole reachable pocket (flood fill), not by touching a single escape — geometrically impossible at that range. | `strategy/encirclement.py::wide_placement` |
| R6 | A wide-range wall must clear both a minimum fraction of the pocket and an absolute floor of cells removed, and must never increase the police's own path length to the target. | `strategy/encirclement.py::MIN_GAIN_FRACTION`, `MIN_GAIN_FLOOR` |
| R7 | In the match's final `ENDGAME_ROUNDS`, the wide-range gain bar loosens — an unused barrier scores nothing at game end, so the tempo cost that protects it earlier no longer applies. | `strategy/encirclement.py::ENDGAME_MIN_GAIN_FLOOR` |
| R8 | Movement tie-breaks among equally-good candidates are broken by a seeded RNG, never by the board's fixed N/S/E/W enumeration order. | `strategy/brain.py::_pick_move` |

## 4. Non-functional requirements

- **Deterministic barrier choice; reproducible movement.** A wall's location
  must be recomputable from the replayed state alone (spec: sealed moves are
  re-checked at audit). Movement is reproducible *per seed*: two brains built
  from identically-seeded generators agree, so a saved seed reconstructs one
  specific game, without every tied step collapsing onto the same direction.
- **Measured, not assumed, thresholds.** `MIN_GAIN_FRACTION`/`MIN_GAIN_FLOOR`
  were set by running the shipped policy against an adversarial,
  always-flee-the-farthest-cell thief across 39 starting positions. The
  course reference's looser equivalent (`min_gain=1` from turn one) converted
  0 of 39 within the move ceiling under the same test — every barrier turn is
  a STAY, and a STAY against a fleeing thief is a full step of ground handed
  back for free, every time it fires.

## 5. Explicit non-goals

- Multi-turn barrier planning (building a wall now for a payoff several turns
  later) — every decision is evaluated against the current state only.
- Coordinating barrier placement with the opponent in any way — the wire
  protocol only ever *declares* a placement after it is made (rule 15/16), it
  never negotiates one.

## 6. Success criteria

Measured against the same adversarial benchmark used to tune the thresholds:
≥ 85% capture rate within the move ceiling, using well under half the
barrier quota on average — barriers spent because they provably help, not
because the quota exists to be spent.
