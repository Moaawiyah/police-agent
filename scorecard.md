# Code Scorecard — Police Agent (P2P Cops-and-Robbers) — 2026-08-12 (updated again)
Tested against the guidelines in `output.md`: Table 5 (quick reference card, line 999) + §17 final
checklist (line 933). This updates the same-day scorecard after completing the docstring pass that
was previously scoped out — every mandatory category is now backed by cited evidence at 5/5.

## Scores
| Category                     | Score |
|-------------------------------|-------|
| Structure & docs              | 5/5   |
| Architecture & code           | 5/5   |
| Tests & quality               | 5/5   |
| Config & security             | 5/5   |
| Research & viz (optional)     | 1/5   |
| Extension & standards (opt.)  | 4/5   |
| **Overall**                    | **25/30 (83%)** |

## Hard-gate checklist (Table 5)
- [x] **Files ≤ 150 non-blank/non-comment lines** — `strategy/belief.py` was 163 such lines; its
  read-side queries were split into `strategy/belief_queries.py` (module-level functions taking the
  grid as their first argument, the same pattern `infra/mcp_client_ops.py` uses for `McpTransport`).
  Every file under `src/` and `tests/` now passes, re-verified after the full docstring pass added a
  line to dozens of files: `find src tests -name '*.py' | while read f; do n=$(grep -vcE
  '^\s*(#.*)?$' "$f"); [ "$n" -gt 150 ] && echo "$n  $f"; done` → no output.
- [x] 0 Ruff violations — `uv run ruff check .` → "All checks passed!" (the enabled rule set in
  `pyproject.toml:43` is `["E","F","W","I","N","UP","B","C4","SIM"]`, which does not include a
  docstring-presence rule like `D` — Ruff itself never caught the docstring gap fixed below)
- [x] Coverage ≥ 85% — 98.10% total (`uv run pytest --cov=src --cov-report=term-missing`), every
  file touched across both fix passes at 100%; the full suite including the `slow`-marked real-socket
  integration tests (`tests/infra/test_mcp_two_peers.py`, `test_live_match.py`) still passes.
- [x] uv.lock + pyproject.toml present; no requirements.txt/poetry.lock/Pipfile
- [x] No secrets in code — 0 matches for hardcoded key/token/password patterns under `src/`
- [x] `.env.example` present at root, documents (accurately) that this project's secrets are
  file-based (`credentials.json`, `token.json`, ngrok's own config), not env vars
- [x] `.gitignore` present, excludes `.env` (`.gitignore:23`) and the credential files above
- [x] README.md + docs/PRD.md + docs/PLAN.md + docs/TODO.md all present
- [x] Rate limits are config-driven, not hardcoded — `config/police/game.json:49`
  (`rate_limiter_gatekeeper`), read via `GateLimits.from_getter` (`shared/gatekeeper_core.py:33-40`)
- [x] **All external calls through the API Gatekeeper** — `infra/mcp_client.py` builds a `Gatekeeper`
  (`peer_gate(config)`) from the same agreed `gatekeeper.*` config keys Gmail and Ollama use,
  injected by `sdk/agent.py`. Every outbound wire call (`negotiate`, `receive_turn`, `receive_control`,
  `submit_audit`) goes through `self._gate.submit(...)` in `_call` before the socket is touched. The
  gate's own `max_retries` is forced to 0 so `_send_with_retry`'s existing retry loop stays the single
  owner of retry timing. Verified against the mocked unit tests and the real two-socket integration
  suite (including its flooding/DoS test). `infra/ngrok_api.py:27` still calls
  `urllib.request.urlopen` directly — left as-is, it's the local ngrok agent's own status API
  (`127.0.0.1:4040`), not a rate-limited third-party endpoint.
- [x] Version module starts at 1.00 — `shared/version.py:13` (`CODE_VERSION = "1.00"`), now matched
  by `pyproject.toml:3` (`version = "1.00"`, was `0.1.0`) and `uv.lock` (regenerated with `uv lock`,
  which normalizes to `1.0` per PEP 440 — the same version, canonical form).

## Qualitative review

**Structure & docs (5/5)** — unchanged. `README.md`, `docs/PRD.md`, `docs/PLAN.md`, `docs/TODO.md`,
per-mechanism PRDs under `docs/mechanisms/`, `docs/ARCHITECTURE.md`'s two Mermaid diagrams, and
`docs/PROMPTS.md` are all present and accurate.

**Architecture & code (5/5, up from 3/5)** — both gaps behind the earlier score are closed:
  - **SDK layering.** The GUI no longer imports `domain`, `peer`, or `strategy` anywhere.
    `gui/replay_data.py` was moved wholesale into `sdk/replay.py` (`normalize_log`, `verify_record`,
    `move_labels`, `opponent_positions`, `frozen_message`, plus a re-export of `BeliefGrid` and its
    `DEFAULT_*` constants). `GameControls` is re-exported from `sdk/agent.py`/`sdk/__init__.py`.
    Verified exhaustively: `grep -rn "^from police_agent\.\(domain\|infra\|peer\|strategy\)"
    gui/*.py` returns nothing, satisfying `sdk/__init__.py`'s own stated rule that consumers "may not
    reach past this layer into peer/ or domain/."
  - **Docstrings.** A static scan of `src/` (`ast.get_docstring` on every public
    `FunctionDef`/`AsyncFunctionDef`/`ClassDef`, dunders included, private `_name`s excluded)
    previously found 157 undocumented items across 52 files. All 157 were given docstrings this pass
    — one line for simple constructors/properties/delegating methods, two to three lines for
    functions with real behavior worth explaining (e.g. `domain/semantic_moves.py::police_turn`,
    `peer/runtime_loop.py::turn_loop`). Re-running the same scan now returns **0**. Every edit was
    checked against the 150-line cap as it went (batched by directory: top-level+domain, gui, infra,
    peer, report+sdk, shared+strategy), and the suite was re-run after each batch — all passed
    throughout. `shared/quota.py::DailyQuota.__init__` was missed on the first pass and caught by the
    final verification scan before being fixed.

  No duplicated business logic was found anywhere in either pass; naming is consistent throughout;
  the two new split-out modules (`sdk/replay.py`, `strategy/belief_queries.py`) follow the existing
  `_ops.py`-style convention already used by `infra/mcp_client_ops.py` rather than inventing a new one.

**Tests & quality (5/5)** — unchanged and, if anything, strengthened across both passes: 98.10%
coverage (every touched file at 100%), 0 Ruff violations, and the real-socket `slow` suite re-run
clean after every batch of changes, including the deliberate-flood DoS test.

**Config & security (5/5)** — unchanged. No hardcoded secrets, `.env.example` and `.gitignore` both
present and accurate, config-driven tunables throughout, uv-only with a committed lockfile.

**Research & viz, optional (1/5)** — unchanged; out of scope for both passes. No `notebooks/`,
`data/`, or `assets/` directory. Explicitly optional in the guideline (§17.5).

**Extension & standards, optional (4/5, up from 3/5)** — the version mismatch is fixed:
`pyproject.toml`'s `version` now reads `1.00`, matching `shared/version.py:13`'s `CODE_VERSION`, and
`uv.lock` was regenerated to match (`uv lock` normalizes the resolved version to `1.0` per PEP 440 —
the same version, canonical form, not a new mismatch). Two items remain, both declined for this pass:
a couple of untidy git commit messages (`64f009c barries logic improvments`, `1005104 gui
enhansments`) — fixing them means rewriting published history, a destructive operation not taken
without explicit confirmation — and no documented extension points or ISO/IEC 25010 mapping, even
though the repo has real extension points worth writing up (`[strategy] police_class` in
`game.toml`, `PoliceBrainBase._pick_move`/`_decide_move` override hooks).

## Verdict
**Meets the submission bar.** Every hard gate in Table 5 passes with cited evidence, and all four
mandatory qualitative categories (Structure & docs, Architecture & code, Tests & quality, Config &
security) score 5/5. The two remaining gaps — Research & viz (1/5) and the rest of Extension &
standards (4/5) — are both explicitly optional in the guideline (§17.5, §17.6) and what's left in
each was left out of scope by choice, not oversight. Nothing here required a rewrite: the fixes were
a file split following an existing pattern, wiring one more channel through code that already
existed, moving one module behind an existing facade, a mechanical (if large) docstring pass, and a
one-line version bump — each verified against the full test suite as it went.
