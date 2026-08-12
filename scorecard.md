# Police Agent quality scorecard — 2026-08-12

This is an internal software-quality assessment, not a course grade and not a declaration
of full submission readiness. The course deliverable also needs live public interoperability,
cross-group evidence, report delivery and release metadata that code-quality checks cannot prove.

## Scores

| Category | Score | Current evidence |
|---|---:|---|
| Structure and documentation | 5/5 | SDK boundary, focused packages, README report and feature documentation |
| Architecture and code | 5/5 | Separate-process design, typed domain model, configurable adapters and extension seam |
| Tests and quality | 5/5 | 1,031 passed, 1 skipped; 98.11% coverage; Ruff and formatting clean |
| Configuration and security | 5/5 | Shared/private config split, ignored secrets, commit-reveal and semantic audit |
| Research and visualization (optional) | 2/5 | Live and verified replay evidence; no notebook or RL experiment because RL was not used |
| Extension and standards (optional) | 4/5 | Custom strategy loading and version alignment; no formal ISO/IEC 25010 mapping |
| **Total** | **26/30 (87%)** | Software quality only |

## Hard gates

- [x] All Python files under `src/` and `tests/` are at most 150 nonblank/noncomment lines.
- [x] `uv run ruff check .` passes.
- [x] `uv run ruff format --check .` passes.
- [x] `uv run pytest` passes: 1,031 passed and 1 skipped.
- [x] Coverage is 98.11%, above the configured 85% minimum.
- [x] `pyproject.toml` and `uv.lock` are present; the package version is `1.00`.
- [x] Private `game.toml`, OAuth credentials, tokens, logs and local reports are ignored.
- [x] CLI and GUI delegate through `PoliceAgentSDK` rather than owning game rules.
- [x] Outbound MCP, Ollama and Gmail calls use configured gatekeepers.
- [x] Live GUI and production-log replay evidence is committed under `assets/`.

## Live evidence boundary

The 2026-08-12 local series ran Police and Thief as separate processes over real localhost
FastMCP endpoints. Police won both sub-games by capture (10 and 9 steps), both peers agreed
on the 40–10 aggregate outcome, and the per-game audits reported verified, untampered logs.
The replay independently recomputed commitments in both production logs and showed
`Verified OK` with both agents visible.

This evidence does not cover an authenticated public tunnel, live Gmail delivery, or two
different external opponent groups. The final-result artifacts also disagree on their
consensus digests even though their visible game facts match.

## Verdict

The repository meets its configured software-quality gates and has fresh local runtime
evidence. It is not yet defensible as a fully submission-ready league release until the
open items in [docs/TODO.md](docs/TODO.md) are completed and recorded.
