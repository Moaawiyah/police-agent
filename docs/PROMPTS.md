# Prompts book

Every prompt this agent ever sends to a language model, verbatim from source.
There are exactly two call sites — both optional flavour text, per Appendix He
25 and ch. 6.5: an LLM shapes *text and behavioural profile* here, never a
move. If no model is reachable, both fall back to deterministic Python (a
canned line; a keyword scan) and the match plays on unaffected.

Default model: `qwen3:4b` via a local Ollama server (`infra/ollama.py`), no
tokens billed, capped at 96 output tokens. Both calls go through the shared
`Gatekeeper` (`shared/gatekeeper.py`) so reading a hint and writing one share
one rate limit and one token tally.

## 1. Writing a trash-talk hint

Source: `strategy/talk.py`, `HintWriter._system()` / `HintWriter._user()`.
Called once per turn (or every `trash_talk.every_n_steps` turns) after the
move has already been decided, applied, and sealed — nothing here can reach
a decision.

**System prompt** (`{setting}` is the private `play.setting` config value,
e.g. `"New York"`; `{max_words}` is the signed `play.hint_max_words` term):

```
You are a police detective chasing a thief through {setting}. Reply with ONE
taunting line of at most {max_words} words. Name a real {setting} landmark.
You may bluff about where you are. Never write grid coordinates, row or
column numbers. Output the line only: no quotes, no preamble, no explanation.
```

**User prompt** (`{mood}` depends on whether this turn's move produced a
capture claim; `{heard}` echoes the thief's last hint if there was one):

```
{mood} {heard}
```

Example, assembled: `"You are closing in fast. The thief just said: \"slipping
past the uptown lights\". Answer it."`

Appendix He 27 forbids numeric locations on the wire. The guarantee against
leaking one is structural, not a filter on the reply: the prompt is never told
a cell, a distance, or the board, so there is nothing spatial for it to leak.
The reply is still sanitised (`strategy/talk_text.py` strips anything
coordinate-shaped) because a model told nothing can still invent something.

## 2. Reading the thief's claimed direction

Source: `strategy/hint_claim.py`, module constant `_SYSTEM` and the f-string
in `claimed_direction()`. Called once per incoming hint, to turn free text
into the one proposition `strategy/bluff.py` can check against the scent
trail: a compass direction, or none.

**System prompt** (fixed, no interpolation):

```
You read one line written by a fleeing thief and decide which compass
direction it claims the thief is heading or standing. The line may be a lie;
you are not judging truth, only what is being claimed. Answer with exactly
one character: N, S, E, W, or - if no direction is claimed. Output that
character and nothing else.
```

**User prompt** (`{text}` is the thief's hint, verbatim):

```
The thief said: "{text}"
```

The reply is parsed for a standalone `N`/`S`/`E`/`W` character
(`hint_claim.py::_from_answer`); anything else — padding, a spelled-out word,
silence, a timeout — falls back to a keyword scan over the same fixed
direction words (`_KEYWORDS`), which is also the entire mechanism when no
model is configured at all.

## What is deliberately never asked

Neither prompt is ever told: the board size, either agent's true position,
the belief map, barrier locations, or the scent field. `strategy/talk.py`'s
own docstring states the principle this book exists to make checkable: *"the
strongest guarantee against leaking [a location] is not to filter the answer
but to never ask the question."*
