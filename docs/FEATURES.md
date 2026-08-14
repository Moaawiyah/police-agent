# Police Agent feature guide

This is the entry point for the implemented Police-agent features. The pages
describe the current checkout, its public entry points, and the evidence that
supports each status. They are implementation documentation, not a replacement
for the official course specification.

## Feature map

| Area | Documentation | Main implementation | Tests and evidence |
|---|---|---|---|
| Core gameplay | [CORE_GAMEPLAY.md](CORE_GAMEPLAY.md) | [`domain/`](../src/police_agent/domain/) and [`constants.py`](../src/police_agent/constants.py) | [`tests/domain/`](../tests/domain/) |
| P2P protocol and transport | [P2P_PROTOCOL.md](P2P_PROTOCOL.md) | [`infra/mcp_client.py`](../src/police_agent/infra/mcp_client.py), [`infra/mcp_server.py`](../src/police_agent/infra/mcp_server.py), [`peer/`](../src/police_agent/peer/) | [`tests/infra/`](../tests/infra/), [`tests/peer/`](../tests/peer/) |
| Commit-reveal and audit | [SECURITY_AND_AUDIT.md](SECURITY_AND_AUDIT.md) and [mechanism PRD](mechanisms/PRD-commit-reveal.md) | [`domain/crypto.py`](../src/police_agent/domain/crypto.py), [`peer/sealing.py`](../src/police_agent/peer/sealing.py), semantic audit modules | [`tests/domain/test_crypto.py`](../tests/domain/test_crypto.py), audit and replay tests |
| Scent and Bayesian belief | [POLICE_STRATEGY.md](POLICE_STRATEGY.md) and [mechanism PRD](mechanisms/PRD-belief-scent.md) | [`domain/scent.py`](../src/police_agent/domain/scent.py), [`strategy/belief.py`](../src/police_agent/strategy/belief.py) | [`tests/domain/test_scent.py`](../tests/domain/test_scent.py), [`tests/strategy/`](../tests/strategy/) |
| Police decision policy | [POLICE_STRATEGY.md](POLICE_STRATEGY.md) and [barrier PRD](mechanisms/PRD-barrier-strategy.md) | [`strategy/`](../src/police_agent/strategy/) | [`tests/strategy/`](../tests/strategy/) |
| Verbal and deception layer | [VERBAL_LAYER.md](VERBAL_LAYER.md) and [PROMPTS.md](PROMPTS.md) | [`strategy/talk.py`](../src/police_agent/strategy/talk.py), [`strategy/bluff.py`](../src/police_agent/strategy/bluff.py), [`infra/ollama.py`](../src/police_agent/infra/ollama.py) | [`tests/strategy/test_talk.py`](../tests/strategy/test_talk.py), bluff and Ollama tests |
| Gatekeeper and token accounting | [GATEKEEPER_AND_TOKENS.md](GATEKEEPER_AND_TOKENS.md) | [`shared/`](../src/police_agent/shared/) and [`infra/ollama.py`](../src/police_agent/infra/ollama.py) | [`tests/shared/`](../tests/shared/), gatekeeper and Gmail-gate tests |
| SDK, CLI, and configuration | [SDK_CLI_CONFIGURATION.md](SDK_CLI_CONFIGURATION.md) | [`sdk/`](../src/police_agent/sdk/), [`__main__.py`](../src/police_agent/__main__.py), [`shared/config.py`](../src/police_agent/shared/config.py) | [`tests/sdk/`](../tests/sdk/), [`tests/shared/test_config.py`](../tests/shared/test_config.py) |
| GUI, replay, and export | [GUI_REPLAY_EXPORT.md](GUI_REPLAY_EXPORT.md) | [`gui/`](../src/police_agent/gui/) and [`peer/view.py`](../src/police_agent/peer/view.py) | [`tests/gui/`](../tests/gui/) |
| Series, artifacts, and email | [REPORTING_AND_SERIES.md](REPORTING_AND_SERIES.md) and [GMAIL_SETUP.md](GMAIL_SETUP.md) | [`report/`](../src/police_agent/report/), [`sdk/reporting.py`](../src/police_agent/sdk/reporting.py), [`infra/gmail.py`](../src/police_agent/infra/gmail.py) | [`tests/report/`](../tests/report/), Gmail and series tests |
| Operations and interoperability | [INTEROPERABILITY_AND_OPERATIONS.md](INTEROPERABILITY_AND_OPERATIONS.md) | [`sdk/league.py`](../src/police_agent/sdk/league.py), [`infra/tunnel.py`](../src/police_agent/infra/tunnel.py), and [`infra/mcp_client.py`](../src/police_agent/infra/mcp_client.py) | socket tests and completed match artifacts when available |

## Status vocabulary

- **Implemented** means the behavior exists in the current source tree.
- **Tested** means automated tests cover the behavior; this does not imply a
  live peer or third-party service was used.
- **Live-verified** is reserved for a completed run with result and audit
  artifacts, not an open port or a process that merely started.
- **Open** identifies a deliberate operational, cross-repository, or live
  service check that still needs to be performed.

## Reading order

Start with [CORE_GAMEPLAY.md](CORE_GAMEPLAY.md), then read
[P2P_PROTOCOL.md](P2P_PROTOCOL.md) and [SECURITY_AND_AUDIT.md](SECURITY_AND_AUDIT.md)
for the match lifecycle. The strategy, front-end, and reporting pages explain
the optional and operational layers around that core.

The high-level requirements remain in [PRD.md](PRD.md), the call-chain diagrams
remain in [ARCHITECTURE.md](ARCHITECTURE.md), and active follow-up work remains
in [TODO.md](TODO.md).
