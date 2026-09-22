# Cost & Pricing Analysis

Scope: the only LLM usage in this repository is the police's verbal layer —
one taunt per turn, written by `strategy/talk.py` (`src/police_agent/strategy/talk.py`).
Appendix He 25 bounds a language model to shaping *text and behavioural
profile* and nothing else; the move itself is always decided in pure Python
before the model is ever asked (`ch. 6.5`). That boundary is also what makes
this cost analysis tractable: there is exactly one call site, and its
maximum output size is fixed in code, not left to the model.

## What a call costs

Every provider call goes through `infra/ollama.py` or `infra/openai_compat.py`,
both capped at `_MAX_TOKENS = 96` completion tokens and both submitted with
reasoning/"thinking" disabled — a fifteen-word taunt needs no chain of
thought, and on the metered path (`openai_compat.py`) thinking tokens are
billed like any other. `config/police/game.toml.example` (`[trash_talk]`,
lines 60-70) additionally exposes `every_n_steps`, which throttles how often
the model is asked at all (default: every step).

Two providers are supported, selected by `provider =` in `game.toml`:

| Provider | Model (default) | $/token | Notes |
|---|---|---|---|
| `ollama` (shipped default) | `qwen3:4b`, local | **$0** | Runs on `localhost:11434`; no network call leaves the machine, no budget to ration — only latency (`infra/ollama.py` docstring). |
| `openai_compat` (z.ai) | `GLM-4.7-FlashX` | metered, provider-billed | Requires `ZAI_API_KEY`; no key is present in this repo's `.env.example`, so this path has never actually been exercised in a recorded match — see caveat below. |
| `template` | none | $0 | Canned lines, no model call at all — same fallback path used automatically when a model is unreachable. |

**Caveat on the metered path:** this repo does not hold a z.ai API key and no
recorded match used it, so a dollar figure here would be invented, not
measured — CLAUDE.md is explicit that this project should not state rules or
numbers it can't ground. What *is* fixed by code, and therefore portable to
any $/1M-token rate a provider publishes: at most 96 completion tokens per
call, plus a short system+user prompt (the measured runs below average ~103
prompt tokens/call). Multiply those token counts by whatever rate api.z.ai
quotes at call time to get a real figure — the code doesn't hide that number,
the repository just hasn't spent one yet.

## Measured cost, per match (real data)

`shared/tokens.py`'s `TokenLedger` records only what the provider itself
reports (`prompt_eval_count`/`eval_count` for Ollama) — never a
character-count estimate — and seals the running total into the signed
end-of-game JSON (Appendix He 54). Two completed matches in `results/` give
real, not estimated, per-match figures:

| Source | Calls | Prompt tokens | Completion tokens | Total tokens | Avg tokens/call |
|---|---|---|---|---|---|
| `results/police-result.json` | 69 | 7,123 | 6,624 | 13,747 | ~199 |
| `results/match_summary.json` | 35 | 3,811 | 3,360 | 7,171 | ~205 |

Both matches ran on the shipped default (`ollama`, local `qwen3:4b`), so both
cost **$0** in API spend — the entire figure above is compute time on the
machine running the match, not billed tokens. It is reported anyway, per
`shared/tokens.py`'s own reasoning: "a ledger measures; it does not enforce,"
and the day this points at a metered provider, the accounting is already
real rather than something added under pressure.

## Per-series budget

Appendix Vav table 18 sets a series budget of **200,000 tokens**. Both
recorded matches used a small fraction of a single sub-game's share of that
(13,747 and 7,171 tokens respectively — under 7% each, and a series is six
sub-games). Nothing in the code enforces this ceiling numerically (the
ledger measures, it doesn't gate — see `shared/tokens.py`), so the real
spend-limiting mechanisms are the ones below.

## What actually keeps spend down (design decisions, with the code that does it)

- **Local-first default.** `provider = "ollama"` ships as the default in
  `config/police/game.toml.example` (line 66) — the metered z.ai path is
  opt-in, not the out-of-box behavior.
- **Hard per-call output cap.** `_MAX_TOKENS = 96` in both
  `infra/ollama.py` and `infra/openai_compat.py` — a hint is capped at
  fifteen words by the agreed terms, so the ceiling matches the actual need
  rather than trusting the model to stop.
- **No reasoning tokens.** Both providers are called with thinking/reasoning
  explicitly disabled, which on the metered path is tokens that would
  otherwise be billed for output the game never uses.
- **Call throttling.** `every_n_steps` in `[trash_talk]`
  (`config/police/game.toml.example` line 70) lets a deployment call the
  model less than once per turn.
- **Gatekeeper + daily quota.** Every call is submitted through
  `shared/gatekeeper.py`/`shared/gatekeeper_core.py`, which rate-limits
  outbound calls, and `shared/quota.py`'s `DailyQuota` enforces a persistent
  daily ceiling (used for Gmail at 20/day in `infra/gmail.py` line 52; the
  same primitive is available to bound any metered provider by day, surviving
  process restarts since each sub-game is its own process).
- **Fail to free, not to blocked.** Any provider failure — missing key,
  unreachable endpoint, timeout, malformed reply — raises one typed error
  (`OllamaError`/`ChatApiError`) that `strategy/talk.py` catches and
  degrades to one of four canned `_FALLBACK_LINES`, costing nothing. A match
  never stalls or fails because a paid model was unavailable.
- **LLM excluded from the rules engine.** The model shapes text only; move
  legality, capture, and scoring are pure Python (`ch. 6.5`), so there is no
  scenario where retrying or upgrading a model is needed to keep the game
  correct — cost pressure never trades against correctness.
- **Honest, provider-reported accounting.** `shared/tokens.py`'s `Usage`
  keeps only what the provider itself reports, sealed per step into the
  signed match record (`peer/sealing.py`) — so the cost figures above are
  independently checkable in `results/`, not self-reported estimates.

## Reproducing these figures

The `tokens` block in any completed match's result JSON
(`results/police-result.json`, `results/match_summary.json`, or any
`logs/<group>/log_*.json`) carries `tokens_total`, `prompt_tokens`,
`completion_tokens`, `model_calls`, and `budget_per_series` directly —
no recomputation needed to audit a specific match's spend.
