# Mechanism PRD — Hint Reading and the Lie Detector

Required by the structure guideline (§17.1): a dedicated PRD per central
algorithm. Scope here is `strategy/bluff.py`, `strategy/hint_claim.py`, and
`strategy/bearings.py`.

## 1. Problem

The specification lets the thief's verbal hint be false (ch. 4.4) and asks
the language model to act as a bluff classifier and behavioural profiler
(ch. 6.5) — but a model can only be a witness, never the judge: its output
must not decide anything on its own, only feed arithmetic that can be
audited later from a replayed log. The police must turn one sentence of free
text into a scored, checkable claim, weigh it against physical evidence
(scent), and track whether this specific opponent's word has been worth
believing so far — all as pure, replayable functions with no model call in
the judging path itself.

## 2. Users

- **`peer/runtime_loop.py`** (or equivalent turn handler) — calls
  `BluffAnalyst.assess` once per turn with the opponent's hint text, the
  currently-believed cell, and the freshest smelled cell, then `.apply` to
  let a corroborated/contradicted verdict move the belief.
- **`strategy/belief.py`** — the target of `.apply`'s `belief.scale(...)`
  call; a believed lie or truth reweights a half-plane of cells, it never
  overwrites the distribution outright.
- **The end-of-game report** — `Verdict.note` is one line per turn, meant to
  be legible in the report/replay without re-deriving the arithmetic.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| L1 | Reduce free text to the smallest checkable proposition: one compass direction, or none. A model is asked first; unparseable, refusing, or absent-model cases fall back to an explicit keyword scan. | `strategy/hint_claim.py::claimed_direction` |
| L2 | Keyword matching requires an unambiguous single direction; several conflicting directions in one sentence resolve to no claim at all, never a guessed majority. | `strategy/hint_claim.py::_from_keywords` |
| L3 | A claim is judged against the freshest cell of the scent that arrived the same turn, not against the belief's argmax — an argmax often will not move on one turn of evidence, which would leave half of all lies undetected. | `strategy/bluff.py::assess`, `strategy/bearings.py::agrees` |
| L4 | Agreement is judged one axis at a time: a north claim against a north-east trail still corroborates; only the exact opposite axis contradicts; movement on the orthogonal axis proves nothing either way. | `strategy/bearings.py::agrees` |
| L5 | When scent arrived this turn, a corroborated/contradicted claim updates this peer's reliability score but does not itself move the belief — the scent is about to move it anyway, and counting the same turn's evidence twice would double-weight it. | `strategy/bluff.py::assess` (comment on `trust`) |
| L6 | When no scent arrived this turn, the claim is the only evidence available, so it moves the belief, weighted by `trust` (this opponent's proven reliability, signed -1..+1). | `strategy/bluff.py::assess`/`apply` |
| L7 | Reliability is Laplace-smoothed (`(corroborated+1)/(corroborated+contradicted+2)`) so an unproven opponent starts at exactly 0.5 (`trust` = 0), and a single corroborated hint is not treated as proof of an honest opponent. | `strategy/bluff.py::reliability` |
| L8 | The move applied to the belief is a half-plane (`bearings.cells_toward`), not a single cell — a bearing is a direction, not an address, and the thief could be anywhere along it. | `strategy/bearings.py::cells_toward` |

## 4. Non-functional requirements

- **The model is a witness, not a judge.** `hint_claim.py` only ever produces
  a direction (or none); every downstream decision — whether it agrees with
  the scent, how much it moves the belief, how it updates reliability — is
  deterministic arithmetic over that direction. A model failure (timeout,
  exception, refusal) degrades to the keyword fallback, never to a lost turn
  or a fatal error.
- **Purity in the judging path.** `bluff.py::assess`/`apply` and
  `bearings.py` take no I/O and make no model call themselves — the model
  call happens once, inside `hint_claim.claimed_direction`, before any
  scoring runs — so a replay recomputes the identical verdict from a saved
  hint, believed cell, and smelled cell with no network involved.
- **Private tuning, not an agreed term.** `bluff.DEFAULT_GAIN` and the
  reliability formula are this peer's own choices; nothing about how hard a
  claim pulls the belief is signed in `peer/terms.py`, matching
  `PRD-belief-scent.md` B8's split between physical constants and private
  belief tuning.

## 5. Explicit non-goals

- Judging whether a hint is *plausible on its face* (e.g. natural-language
  sentiment) — the only evidence a claim is checked against is where the
  scent actually is.
- Modelling the opponent's strategy for when it chooses to lie — the
  reliability score is a record of outcomes, not a predictive model of
  intent.
- Correcting for an opponent that never claims a direction at all — such a
  peer simply never accrues a reliability signal either way (`trust` stays
  at whatever it last was, and unscored hints do not move it).

## 6. Success criteria

`tests/strategy/test_bluff.py` pins: a corroborated/contradicted claim is
scored correctly per axis, a diagonal still corroborates on the claimed
axis, reliability starts unproven at 0.5 and moves off it only after
evidence, one honest hint alone is not enough to call an opponent honest,
and a claim the scent already answered this turn does not also move the
belief. `tests/strategy/test_hint_claim.py` pins the keyword fallback path
independent of any model. `tests/strategy/test_bluff_belief.py` pins that an
applied verdict reweights the correct half-plane in `belief.py`.
