# Verbal interaction and deception analysis

## Role of language

Language is optional flavor and evidence. It never chooses the Police move,
changes a legal action, or receives the private board state. The move is
decided, applied, and sealed before the outgoing taunt is generated.

## Outgoing hint writer

`HintWriter` can call a local Ollama model or use a deterministic template.
The prompt supplies the setting, the signed word limit, the current mood, and
the thief's previous hint. It does not supply coordinates, distances, the
belief map, barriers, or the board. The reply is sanitized and capped before
it reaches the wire. Any Ollama failure falls back to a canned line so the
match continues.

## Incoming hint classifier

`hint_claim.py` turns a thief hint into one compass claim (`N`, `S`, `E`, `W`,
or no claim). A configured language model is attempted first; standalone
direction parsing and keyword fallback keep the behavior bounded when the
model is unavailable. `BluffAnalyst` then compares the claim with scent
evidence and records whether the claim was corroborated.

The exact prompts are preserved in [PROMPTS.md](PROMPTS.md).

## Gate and accounting

Both language operations share one runtime `Gatekeeper` and one token ledger.
This prevents hint reading and hint writing from bypassing the same provider
limits. Ollama's reported `prompt_eval_count` and `eval_count` are recorded;
token use is not estimated from character length. See
[GATEKEEPER_AND_TOKENS.md](GATEKEEPER_AND_TOKENS.md).

## Configuration

The private `[trash_talk]` block selects `ollama` or `template`, model, URL,
timeout, and frequency. A normal run does not require Ollama or Google
credentials. The language model configured in `[llm]` is identity/reporting
metadata; it is not the authoritative move engine.

## Implementation and tests

- [`strategy/talk.py`](../src/police_agent/strategy/talk.py) and
  [`strategy/talk_text.py`](../src/police_agent/strategy/talk_text.py)
- [`strategy/hint_claim.py`](../src/police_agent/strategy/hint_claim.py) and
  [`strategy/bluff.py`](../src/police_agent/strategy/bluff.py)
- [`infra/ollama.py`](../src/police_agent/infra/ollama.py)
- Talk, prompt, bluff, and Ollama tests under
  [`tests/strategy/`](../tests/strategy/) and [`tests/infra/`](../tests/infra/)

## Open boundaries

The live model path needs an Ollama rehearsal before it can be called
live-verified. The replay summary does not currently retain every outgoing
hint, so the replay viewer can prove the sealed game path without reproducing
all verbal output.
