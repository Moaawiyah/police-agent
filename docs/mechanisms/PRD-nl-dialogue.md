# Mechanism PRD — Verbal Hint Generation

Required by the structure guideline (§17.1): a dedicated PRD per central
algorithm. Scope here is `strategy/talk.py`, `strategy/talk_text.py`, and
`strategy/talk_asker.py`.

## 1. Problem

The specification allows one free-text cue per turn and explicitly permits
it to mislead (ch. 4.4), while Appendix He 25 bounds a language model's role
to shaping *text and behavioural profile* only — it must never be able to
reach a movement or barrier decision, and Appendix He 27 forbids the wire
from ever carrying a numeric location. A model that is asked to be clever
can leak a coordinate anyway (by inventing one, not by being told one), and
a model that is down, slow, or babbling must not be allowed to cost the
match. The hint's Intent (honest or a lie, ch. 5.3.1) must also be fixed
*before* the model speaks, so it can never be claimed after the fact from
whatever the model happened to say.

## 2. Users

- **`peer/turn_sender.py`** — calls the resolved `HintWriter` only after the
  move for the turn has already been decided, applied, and sealed, so
  nothing the model returns can influence that turn's decision.
- **`peer/sealing.py`** — seals the returned `(text, intent)` pair alongside
  the turn's commit, per ch. 5.3.1's `H = SHA256(State | Move | Intent |
  Nonce)` formula.
- **`strategy/bluff.py`** (opposing peer's copy) — reads this peer's hint
  text back out on the wire and judges it against scent; see
  `PRD-bluff-detection.md`.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| V1 | The Intent (truth/lie) is chosen by a coin flip *before* the model is asked, at a configured `bluff_rate`; the model is then told which line to write, never judged afterward on what it said. | `strategy/talk.py::HintWriter.__call__` |
| V2 | The prompt discloses only the setting name, whether the police is "closing in" (a boolean derived from a capture claim, never a cell or distance), and the opponent's last hint — never a cell, a distance, or the board. | `strategy/talk.py::HintWriter._user` |
| V3 | The reply is capped at an agreed word count (`play.hint_max_words`, a signed term — both peers hold the same cap) regardless of how long the model's answer was. | `strategy/talk_text.py::_cap` |
| V4 | Chain-of-thought / reasoning blocks (`<think>...</think>`, including one truncated mid-block with no closing tag) are stripped before anything reaches the wire. | `strategy/talk_text.py::_clean` |
| V5 | A reply containing anything that reads as a grid reference — bare `row, col` pairs, or a labelled `row/column/cell/square/tile/grid` number — is discarded entirely and replaced by the fallback, rather than partially redacted; a landmark that merely contains a digit (e.g. "5th Avenue") survives. | `strategy/talk_text.py::_COORDINATES` |
| V6 | Any failure of the model call (exception, timeout, empty reply, a reply that was nothing but a stripped coordinate) falls back to one of four canned, location-free lines and is always sealed as `TRUTH` — a fallback makes no claim, so there is nothing to declare a lie about. | `strategy/talk.py::HintWriter._fallback`/`__call__` |
| V7 | The model speaks at most once every `every_n_steps` turns (an agreed cadence knob); turns in between use the fallback without attempting a call. | `strategy/talk.py::HintWriter.__call__` |
| V8 | `resolve_hint_writer` shares one rate gate and one token ledger with `strategy/bluff.py`'s asker when the runtime supplies them — writing a hint and reading one are two calls against a single per-peer budget, not two independent ones. | `strategy/talk.py::resolve_hint_writer`, `strategy/talk_asker.py::asker_from_config` |
| V9 | An unrecognised or `"template"` provider in this peer's private config keeps the canned lines and reaches no model at all, on the same code path as a configured-but-unreachable model — a typo costs banter, never the match. | `strategy/talk_asker.py::asker_from_config` |

## 4. Non-functional requirements

- **The model shapes text only.** No function in this scope returns
  anything that feeds movement, barrier placement, or belief update — the
  hint text and its sealed Intent are the entire output, matching Appendix
  He 25 and the module's own stated ordering (called only after the move is
  already sealed).
- **Fail-safe, not fail-loud, toward the match.** Every model failure mode
  (`ConnectionError`, timeout, refusal, empty string, coordinate-only reply)
  degrades to the same fallback path and the same `TRUTH` seal — there is no
  failure mode that raises out of `HintWriter.__call__` or stalls a turn.
- **Provider-agnostic.** `talk_asker.py` returns the same bound
  `ask(prompt, system)` signature for both the hosted (GLM) and local
  (Ollama) providers, so `talk.py` and `bluff.py` never know or care which
  one answered — only the default timeout differs, since a network round
  trip is not a loopback one.

## 5. Explicit non-goals

- Using the model to decide whether to lie *this specific turn* based on
  game state — the Intent coin flip is independent of position, belief, or
  pressure (`capture_claim` only shapes the mood of the prompt, not the
  Intent).
- Guaranteeing the model never *attempts* to leak a coordinate — the
  guarantee is that the sanitiser catches and discards it (V5), not that the
  prompt makes the attempt impossible.
- Multilingual or persona-configurable dialogue — one system prompt, one
  voice ("a police detective"), fixed in code.

## 6. Success criteria

`tests/strategy/test_talk.py` pins: the word cap survives any reply length,
reasoning blocks never leak (including a truncated one), every tested
coordinate-shaped reply is stripped while a landmark with a digit survives,
every model failure mode falls back to a non-empty line, the cadence knob is
honoured, and Intent is sealed correctly at `bluff_rate` 0.0, 1.0, and on the
fallback path. `tests/strategy/test_talk_prompt.py` pins what the prompt
does and does not disclose.
