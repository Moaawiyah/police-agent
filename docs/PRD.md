# Product Requirements — Police Agent

Required by specification ch. 9.4.1. Scope is the **police agent only**; the
thief agent is a separate product in a separate repository.

## 1. Problem

Two autonomous agents must play a pursuit game on a shared discrete grid with
**no central server and no referee**. Neither side trusts the other's client, so
every claim has to be either independently derivable from agreed rules or
cryptographically provable after the fact. The police agent must chase and
capture a thief whose position it never directly observes.

## 2. Users

- **The police agent itself** — runs autonomously for a whole match.
- **The opposing thief agent** — any group's implementation, so the wire
  protocol and the agreed rules file must be honoured exactly.
- **The grader** — must be able to reproduce a match from the repository, the
  signed logs and the replay viewer.

## 3. Functional requirements

| # | Requirement | Source |
|---|---|---|
| F1 | Move one cell orthogonally, or hold. No diagonals. | 3.4, App. ו t.15 |
| F2 | Place a barrier on the cell underfoot or any of the four adjacent cells, forgoing the step. | 3.4 |
| F3 | Truthfully declare every barrier placement and its exact cell. No hidden barriers. | 3.4 |
| F4 | Respect the agreed barrier quota. | 3.4, App. ו t.15 |
| F5 | Issue capture claims and accept the thief's signed answer. | 3.5 |
| F6 | Host a FastMCP server exposing `receive_move`; act as MCP client to the opponent. | ch. 2 |
| F7 | Sign every move (SHA-256 commit-reveal, nonce anti-replay) and verify the opponent's. | ch. 5 |
| F8 | Re-verify the thief's revealed log at the end-of-game audit, including its answers to capture claims. | 3.5, ch. 5 |
| F9 | Emit scent and maintain a Bayesian belief map over the thief's location. | ch. 4, 6 |
| F10 | Score outcomes per the agreed table and emit the result JSON. | 3.5, App. ו t.17 |
| F11 | Send the automated match report via Gmail API in the signed JSON format. | ch. 9 |
| F12 | Provide a live GUI belief map and a replay viewer showing `Verified OK`. | ch. 7 |

## 4. Non-functional requirements

- **Determinism.** The rules engine must be deterministic and independent of
  networking, GUI and LLM code. An LLM is never the authoritative move engine.
- **Isolation.** No shared memory, shared live-state module, or shared variables
  with the thief agent (ch. 2.4.2). Enforced here by the two-repository split.
- **Quality gates.** ≥ 85% test coverage, zero Ruff violations, ≤ 150 lines per
  Python file.
- **Secrets.** No credentials in the repository or its history.

## 5. Explicit non-goals

- Implementing the thief agent (separate repository).
- Using an LLM to decide moves — LLM use is limited to optional flavour text.
- Any central referee, shared board object, or authoritative third party.

## 6. Success criteria

A full match against another group's thief agent completes without protocol
violation, the audit reports `Verified OK` on both sides, the result JSON is
accepted, and the report email is delivered.

## 7. Mechanism-level PRDs

The three central algorithms each have their own dedicated requirements
document, one level more specific than this project-wide one:

- [`mechanisms/PRD-belief-scent.md`](mechanisms/PRD-belief-scent.md) — the
  pheromone field and the Bayesian belief map (F9).
- [`mechanisms/PRD-barrier-strategy.md`](mechanisms/PRD-barrier-strategy.md)
  — barrier placement, close-range and wide-range (F2–F4).
- [`mechanisms/PRD-commit-reveal.md`](mechanisms/PRD-commit-reveal.md) — the
  cryptographic seal-and-audit protocol (F7, F8).
