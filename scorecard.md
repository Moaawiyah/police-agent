# Code Scorecard — Police Agent — 2026-08-22

Tested against the guidelines in `output.md` (Table 5 — כרטיס עזר מהיר, and §17 final
checklist). This is a software-quality assessment only: it does not certify the course
deliverables that code checks cannot prove (live public interoperability, cross-group
match evidence, report delivery, release metadata). See `docs/TODO.md` and the
"Known gaps" section of `README.md` for those.

## Scores

| Category                              | Score |
|---------------------------------------|-------|
| Structure & docs (§17.1)              | 5/5   |
| Architecture & code (§17.2)           | 5/5   |
| Tests & quality (§17.3)               | 5/5   |
| Config & security (§17.4)             | 5/5   |
| Research & viz (§17.5, optional)      | 5/5   |
| Extension & standards (§17.6, optional) | 5/5 |
| **Overall**                           | **30/30 (100%)** |

## Hard-gate checklist (Table 5)

- [x] **SDK architecture** — all logic through the SDK. `PoliceAgentSDK`
      (`src/police_agent/sdk/agent.py:33`) is the public boundary; `__main__.py:29` and
      the GUI both enter through it. No module under `gui/` reaches past the SDK.
- [x] **OOP / no duplication** — automated AST scan over all 134 `src/` modules found
      **0** duplicated function bodies of ≥4 statements.
- [x] **API gatekeeper** — every outbound provider call is admitted through
      `shared/gatekeeper.py`: Ollama (`infra/ollama.py:133`), OpenAI-compatible
      (`infra/openai_compat.py:136`), Gmail (`infra/gmail.py:131`), MCP peer
      (`infra/mcp_client.py:70`). One localhost exception, noted below.
- [x] **Rate limits from config, not code** — `GateLimits.from_getter`
      (`shared/gatekeeper_core.py:33`) reads the agreed `rate_limiter_gatekeeper` block
      in `config/police/game.json:49`.
- [x] **Queue management** — overload queues rather than crashes:
      `AdmissionQueue` (`shared/admission.py:36`) is FIFO over a token bucket and a
      concurrency cap; only a full backlog (`depth`) is refused, and it is refused with
      a typed `GatekeeperOverloadError`, not a crash.
- [x] **Version control starts at 1.00** — `CODE_VERSION = "1.00"`
      (`shared/version.py:13`), matching `pyproject.toml:3`.
- [x] **TDD** — 140 test files against 134 source modules; per-package test dirs mirror
      `src/` (`tests/domain`, `tests/peer`, `tests/sdk`, `tests/strategy`, …).
- [x] **File size ≤ 150 lines** — **0 violations** by the guideline's measure
      (non-blank, non-comment lines) across all 299 `.py` files in `src/` and `tests/`.
      Largest source file is now `team_sync/scheduler_helpers.py` at 145.
- [x] **0 Ruff violations** — `uv run ruff check .` → *All checks passed!*
      `uv run ruff format --check .` → *322 files already formatted*.
- [x] **Coverage ≥ 85%** — `uv run pytest --cov=src` → **95.37%** over `src/` + `research/`;
      **93%** with the `omit` list disabled. 1242 tests passed, 0 failed, 0 skipped.
- [x] **0 hardcoded secrets** — grep for `sk-*`, `AKIA*`, `ghp_*` and
      `(api_key|password|secret|token) = "<literal>"` across `src/`, `tests/`, `config/`
      returned nothing. `git log --all --diff-filter=A` confirms `.env`,
      `credentials.json` and `token.json` were **never committed**.
- [x] **.env.example present** — documents the credential boundary with placeholders
      only; explicitly states no secret-bearing env var exists.
- [x] **uv as sole package manager** — `uv.lock` + `pyproject.toml` present; no
      `requirements.txt`, `poetry.lock`, `Pipfile` or `setup.py`.
- [x] **Mandatory docs** — `README.md` (user-guide level) plus `docs/PRD.md`,
      `docs/PLAN.md`, `docs/TODO.md`, `docs/ARCHITECTURE.md` (2 mermaid diagrams),
      `docs/PROMPTS.md` (prompts book), and 3 per-mechanism PRDs under
      `docs/mechanisms/`.
- [x] **Docstrings** — every module, class and public callable in `src/` has one
      (AST-verified: 0 missing). 90 private `_`-prefixed helpers omit them by choice.

**Every Table 5 hard gate passes.**

## Closed in this pass

**§17.5 Research & visualisation (3 → 5).** Built [`research/`](research/) — a
reproducible sensitivity study over all nine tunable constants, 500 episodes per
point against a synthetic evader, with 95% confidence intervals. Deliverables:
15 figures in `assets/`, raw numbers in `docs/research-data.json`, a runnable
[notebook](notebooks/sensitivity.ipynb), and the written analysis in
[docs/RESEARCH.md](docs/RESEARCH.md). The package is 99% covered by 32 new tests
and is measured by the coverage gate alongside `src/`.

Real findings, not a box-tick: `smell_power = 6` beats the shipped 3 on every
metric with disjoint intervals; `TOP_K = 1` beats the shipped 3 by ~8 points;
`WIDE_REACH ≤ 1` collapses the capture rate to 0.2%, showing barriers are the
entire win condition against a competent evader; and four constants have no
measurable effect at all, one of which independently confirms the benchmark
already noted at `encirclement.py:44`. No default was changed — the evader is a
fixture, not a thief, and §5 of the write-up says so explicitly.

**§17.6 Extension & standards (3 → 5).** Added the [MIT LICENSE](LICENSE),
[docs/EXTENSION_POINTS.md](docs/EXTENSION_POINTS.md) (six documented seams plus
one honest non-seam), [docs/ISO25010.md](docs/ISO25010.md) (all eight
characteristics mapped to evidence, with four gaps named rather than hidden),
and [.github/workflows/quality.yml](.github/workflows/quality.yml) running all
four gates on push.

**Earlier in the session.** Coverage omit list narrowed to the four Tk-widget
modules; the SDK-layering leak in `gui/game_mode.py` closed; 12 missing
docstrings added; `ruff format` applied, which forced a 150-line split of
`scheduler_helpers.py` into `scheduler_send.py`.

## What the score does not cover

The scorecard measures code quality. It does **not** certify submission
readiness, and four items in [docs/TODO.md](docs/TODO.md) still block that:

1. **No protocol state machine.** Appendix He rules 4 and 5 both require one
   (sanctions: technical loss, and a logic error leading to a loss). The sibling
   thief repo has `domain/state_machine.py`; this repo's only transition logic is
   `team_sync/state.py`, which governs series *scheduling*, not the match/turn
   protocol. The highest-value item left in the repo.
2. Public matches against two different external groups, on live tunnels.
3. One real Gmail send with the `gmail.send` scope.
4. The annotated `v1.0-submission` tag, after 1–3 pass.

The final-result consensus digests are **not** an open defect: `a613b6f` fixed the
`roles_of()` keying direction and verified `mutual_agreement.sha256` /
`interop_sha256` byte-for-byte against both the sibling thief and an independently
written third implementation.

One further gap, found while reviewing the tunnel code and recorded in TODO:
`--league` hard-requires ngrok (`sdk/league.py:13`), so a self-managed tunnel
cannot use league mode and silently loses the public-opponent-URL check and the
turn/watchdog timeout guard.

## Verdict

**30/30 on code quality; all Table 5 hard gates pass with margin.** 1242 tests
green, 0 Ruff violations, formatting clean, 0 files over the line budget, 95.37%
coverage against an 85% floor, full docstring coverage, no secret ever committed.
Remaining work is evidence and one interop defect — neither of which a code
scorecard can close.
