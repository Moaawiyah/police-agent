# Code Scorecard — Police Agent — 2026-08-23

Tested against the guidelines in `output.md` (Table 5 — כרטיס עזר מהיר, and §17 final
checklist). This is a software-quality assessment only: it does not certify the course
deliverables that code checks cannot prove (live public interoperability, cross-group
match evidence, report delivery, release metadata). See `docs/TODO.md` and the
"Known gaps" section of `README.md` for those.

Re-run of the 2026-08-22 scorecard. Working tree is clean (`git status`) and no
commits have landed since, so this pass independently re-verifies the same state
rather than re-scoring a changed codebase.

## Scores

| Category                                | Score |
|------------------------------------------|-------|
| Structure & docs (§17.1)                | 5/5   |
| Architecture & code (§17.2)             | 5/5   |
| Tests & quality (§17.3)                 | 5/5   |
| Config & security (§17.4)               | 5/5   |
| Research & viz (§17.5, optional)        | 5/5   |
| Extension & standards (§17.6, optional) | 5/5   |
| **Overall**                             | **30/30 (100%)** |

## Hard-gate checklist (Table 5)

- [x] **SDK architecture** — all logic through the SDK. `PoliceAgentSDK`
      (`src/police_agent/sdk/agent.py:33`) is the public boundary; `__main__.py` and
      the GUI both enter through it.
- [x] **API gatekeeper** — every outbound provider call is admitted through
      `shared/gatekeeper.py`: Ollama (`infra/ollama.py:128`), OpenAI-compatible
      (`infra/openai_compat.py:131`), Gmail (`infra/gmail.py:142`), MCP peer
      (`infra/mcp_client.py:40`) — verified by grep, all four import and construct
      `Gatekeeper` rather than calling out directly.
- [x] **Rate limits from config, not code** — `GateLimits.from_getter`
      (`shared/gatekeeper_core.py`) reads the `rate_limiter_gatekeeper` block in
      `config/police/game.json`, not literals in source.
- [x] **Queue management** — `shared/admission.py` implements a FIFO `AdmissionQueue`
      over a token bucket; overload raises a typed `GatekeeperOverloadError` rather
      than crashing or silently dropping.
- [x] **Version control starts at 1.00** — `CODE_VERSION = "1.00"`
      (`shared/version.py:13`), matching `pyproject.toml:3` (`version = "1.00"`).
- [x] **File size ≤ 150 lines** — 0 violations (non-blank, non-comment count) across
      every `.py` file in `src/`, `tests/`, and `research/`. Largest file is
      `team_sync/scheduler_helpers.py` at 145 lines.
- [x] **0 Ruff violations** — `uv run ruff check .` → *All checks passed!*
- [x] **Coverage ≥ 85%** — `uv run pytest --cov=src --cov-report=term-missing` →
      **95.17%** total (4452 statements, 215 missed), exit code 0, all tests passing.
      Required threshold (85%) reached.
- [x] **0 hardcoded secrets** — grep across `src/` for `api_key=`, `password=`,
      `token=`, `secret=`, `sk-*` literals returned nothing.
- [x] **`.env.example` present, placeholders only** — documents that this project
      keeps credentials in gitignored files (`credentials.json`, `token.json`), not
      env vars, and states that boundary explicitly rather than leaving it implicit.
- [x] **`.gitignore` present and correct** — excludes `.env`, `credentials.json`,
      `token.json`, `*token*.json`, and generated artifacts (`logs/`, `results/`,
      `.coverage`). `git check-ignore -v` confirms all three live credential files
      are ignored and `git log --all` shows none was ever committed.
- [x] **uv as sole package manager** — `uv.lock` + `pyproject.toml` present; no
      `requirements.txt`, `poetry.lock`, or `Pipfile` anywhere in the tree.
- [x] **Mandatory docs present** — `README.md` at root, plus `docs/PRD.md`,
      `docs/PLAN.md`, `docs/TODO.md`, `docs/ARCHITECTURE.md`, `docs/PROMPTS.md`, and
      3 per-mechanism PRDs under `docs/mechanisms/`.
- [x] **Docstrings** — every one of the 134 `src/` modules opens with a module
      docstring (checked via `head -1` scan for `"""`; 0 missing).

**Every Table 5 hard gate passes.**

## Qualitative review (§17.2–17.3)

- **OOP / DRY** — shared cross-cutting concerns (gatekeeper, rate limiting, quota,
  version, schema) live once in `shared/`, imported by every consumer in `infra/`,
  `peer/`, and `sdk/` rather than reimplemented per call site.
- **Research & visualisation (§17.5)** — `research/` package (grid, evader, harness,
  sweeps, plots) backs a reproducible sensitivity study; `notebooks/sensitivity.ipynb`
  and `docs/research-data.json` hold the run artifacts; `docs/RESEARCH.md` is the
  written analysis.
- **Extension & standards (§17.6)** — `LICENSE` (MIT), `docs/EXTENSION_POINTS.md`,
  `docs/ISO25010.md`, and `.github/workflows/quality.yml` (CI running the same four
  Table 5 gates — lint, format, file size, coverage — on every push) are all present
  and match what they claim to do.

## What the score does not cover

The scorecard measures code quality, not submission readiness. Per `docs/TODO.md`,
items outside a code check's reach still remain open: a protocol state machine for
Appendix He rules 4–5, live public matches against two external groups, one real
Gmail send with the `gmail.send` scope, and the annotated `v1.0-submission` tag.

## Verdict

**30/30 on code quality; all Table 5 hard gates pass with margin.** Ruff clean,
0 files over the 150-line budget, 95.17% coverage against an 85% floor, full module
docstring coverage, and no secret ever committed. This re-run found no regression
since the 2026-08-22 scorecard. Remaining work is protocol/interop evidence that a
code scorecard cannot certify.
