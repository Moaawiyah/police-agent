# Gatekeeper, quotas, and token accounting

## Scope

The gate protects calls to third-party services such as local Ollama and Gmail
provider APIs. The Police-to-opponent MCP transport is intentionally outside
this gate: delaying a legal turn to protect a third-party quota could trigger
the opponent's watchdog and lose the match.

## Admission path

An outbound call passes through the following policy:

1. Check the DOS/anomaly detector.
2. Enter the bounded FIFO admission queue.
3. Wait for the concurrency slot and token-bucket allowance.
4. Call the provider.
5. Retry bounded failures with backoff while the time budget remains.

Queue overload is handled according to the configured depth; legal work is not
silently dropped. The detector and bucket expose measurements, while
`Gatekeeper` applies the policy and reports counters.

## Inbound observation

The runtime observes the opponent's incoming message rate with a separate DOS
detector. A suspicious reading is reported in `inbound_dos`; the runtime does
not drop a legal turn merely because it suspects a flood.

## Quota and token ledger

The optional daily quota is persisted so separate sub-game processes share the
same count. It is spent before the provider gate. `TokenLedger` records the
provider-reported prompt and evaluation counts for each model call and exposes
per-match totals in the summary. A peer's token spend is not guessed or
claimed; it is reported as unavailable/zero according to the artifact contract.

## Configuration and output

The signed `rate_limiter_gatekeeper` terms define shared limits. Private
provider and Gmail settings remain in `game.toml`. Match summaries include
`tokens`, `gatekeeper`, and `inbound_dos` blocks so a grader can inspect what
actually passed through the gate.

## Implementation and tests

- [`shared/gatekeeper.py`](../src/police_agent/shared/gatekeeper.py),
  [`shared/gatekeeper_core.py`](../src/police_agent/shared/gatekeeper_core.py),
  [`shared/admission.py`](../src/police_agent/shared/admission.py),
  [`shared/rate_limit.py`](../src/police_agent/shared/rate_limit.py),
  [`shared/quota.py`](../src/police_agent/shared/quota.py), and
  [`shared/tokens.py`](../src/police_agent/shared/tokens.py)
- Runtime integration: [`peer/summary.py`](../src/police_agent/peer/summary.py)
  and [`infra/ollama.py`](../src/police_agent/infra/ollama.py)
- Tests: [`tests/shared/`](../tests/shared/) plus gate tests under
  [`tests/infra/`](../tests/infra/)

## Open boundaries

`max_retries` is a ceiling, not a promise that every call reaches that count:
the deadline can end the attempt earlier. Public performance and provider
quota behavior still need live validation with the selected service account.
