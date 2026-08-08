# Code Scorecard — Police Agent (P2P Cops-and-Robbers) — 2026-08-08 (updated)
Tested against the guidelines in output.md (Table 5, ~line 999 + §17, ~line 933).
This is a re-verification after fixing every gap the first pass found.

## Scores
| Category               | Score |
|-------------------------|-------|
| Structure & docs        | 5/5   |
| Architecture & code     | 5/5   |
| Tests & quality         | 5/5   |
| Config & security       | 5/5   |
| Research & viz (opt.)   | 1/5   |
| Extension & standards (opt.) | 4/5 |
| **Overall**              | **25/30 (83%)** |

## Hard-gate checklist (Table 5)
- [x] Files ≤ 150 non-blank/non-comment lines — all pass (the 3 oversized test files were split three ways: `test_agent.py`/`test_agent_league.py`/`test_agent_lifecycle.py` + `tests/sdk/conftest.py`; `test_result.py`/`test_result_digest.py`; `test_artifacts.py`/`test_artifacts_log.py`)
- [x] 0 Ruff violations — `uv run ruff check .` → "All checks passed!"
- [x] Coverage ≥ 85% — 97.95% (`uv run pytest --cov=src --cov-report=term-missing`)
- [x] uv.lock + pyproject.toml present, no requirements.txt/poetry.lock/Pipfile
- [x] No secrets in code — 0 matches
- [x] `.env.example` present — added, documents the project's file-based secrets (`credentials.json`, `token.json`, ngrok's own config) since no env var actually carries one
- [x] `.gitignore` present and excludes `.env`/credentials
- [x] README.md + docs/PRD.md + docs/PLAN.md + docs/TODO.md present
- [x] Rate limits/config-driven, not hardcoded
- [x] All external calls through the API Gatekeeper
- [x] Version module starts at 1.00

## What was fixed since the first pass

1. **File size hard gate** — split all 3 oversized files (929 tests now pass, up from 867 before this session's other work; every file under 150 lines, verified by the same non-blank/non-comment count the guideline specifies).
2. **`.env.example`** — added at project root.
3. **Automated test-report artifact** — `[tool.coverage.html]` added to `pyproject.toml`; README documents `--cov-report=html` (→ `htmlcov/index.html`) and `--junit-xml=results/junit.xml`, both verified to actually generate.
4. **Per-mechanism dedicated PRDs** — added `docs/mechanisms/PRD-belief-scent.md`, `PRD-barrier-strategy.md`, `PRD-commit-reveal.md`, linked from `docs/PRD.md`.
5. **Architecture diagram** — added `docs/ARCHITECTURE.md`: a Mermaid sequence diagram of the wire protocol (handshake → turn loop → audit) and a flowchart of one police turn's decision pipeline (scent → belief → brain → barrier/movement).
6. **Prompts book** — added `docs/PROMPTS.md`: both LLM call sites (`strategy/talk.py`'s trash-talk hint, `strategy/hint_claim.py`'s direction classifier) reproduced verbatim from source, with the "never ask the question" rationale for why neither prompt is ever told a location.

## Remaining gap (optional category)

- **Research & visualization (§17.5, optional)** — still no persisted analysis
  notebook. This session ran substantial empirical parameter sweeps (scent
  normalization, barrier gain thresholds, endgame relaxation, movement
  tie-break randomization) that directly shaped the shipped defaults, but all
  of it lived in ephemeral scratch scripts outside the repository. Turning
  those into a permanent, reproducible notebook is a real but separate task
  from anything the hard gates require — left as-is pending a decision on
  scope.

## Verdict
**Meets** the submission bar. Every hard gate in Table 5 now passes with
cited evidence, and all four required qualitative categories score 5/5. The
one remaining gap is explicitly optional in the guideline (§17.5) and does
not affect runtime correctness, test coverage, or any of the mandatory
documentation.
