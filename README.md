# Police Agent — P2P Cops-and-Robbers

The **Police** agent for a distributed Cops-and-Robbers game played over a
peer-to-peer network. This repository contains the police side only.

> **Companion repository (Thief agent):**
> **https://github.com/Moaawiyah/Ai_thief**
>
> The specification (ch. 9.4) requires each group to submit two separate
> repositories, police and thief, with each README cross-linking to the other.

There is no central game server and no referee. Each agent hosts its own
[FastMCP](https://github.com/jlowin/fastmcp) server and acts as an MCP client
toward its opponent; both sides derive the same outcome from a signed, shared
rules file (`config/police/game.json`) and verify each other's moves
cryptographically.

## Why two repositories

Specification ch. 2.4.2 makes the separation mandatory: police code and thief
code must run in **two completely separate processes** under separate config
directories. Sharing memory, importing a shared module holding live state, or
reading shared variables between the sides disqualifies the solution *even if
the game technically works*, because it hands one agent a back door into its
opponent's local truth. Two repositories enforce that structurally.

A visible consequence is in `domain/rules.py`: the two barrier-related capture
rules (Appendix ה, 46 and 47) are absent here by design. Both are conditions the
*thief* evaluates about itself — the police never learns the thief's position
during play and so cannot compute either. The police receives them as signed
claims and re-verifies them at the end-of-game audit.

---

## Academic report

The six sections below are mandatory per specification ch. 9.4.2. They are
filled in as the corresponding build steps land.

### 1. Dec-POMDP model
_Pending — arrives with the belief system (step 6)._ The game is modelled as a
two-agent Dec-POMDP `⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩` with `n = 2`, in which each
agent observes only its own local scent signal rather than the true board state.

### 2. FastMCP orchestration dilemmas
_Pending — arrives with P2P communication (step 4) and orchestration (step 8)._

### 3. Strategies implemented
_Pending — arrives with the police strategy (step 7)._

### 4. Learning curves
_Not applicable unless a reinforcement-learning agent is trained._

### 5. Screenshots
_Pending — requires the live GUI belief map and the Replay App showing
`Verified OK` (step 8)._

### 6. Companion repository link
Thief agent: **https://github.com/Moaawiyah/Ai_thief**

---

## Current status

**Step 2 of 9 complete.** The deterministic domain layer is implemented and
tested; networking, security, belief and strategy are not. See
[docs/PLAN.md](docs/PLAN.md) for the build order, [docs/TODO.md](docs/TODO.md)
for the active step, and [docs/PRD.md](docs/PRD.md) for the product
requirements.

## Layout

```
src/police_agent/
  constants.py  roles, action types, the four legal directions
  domain/       board geometry, actions, own state, rules, scoring
  infra/        FastMCP server/client, email, LLM provider (not implemented)
  peer/         orchestration, handshake, turn handling (not implemented)
  shared/       config loading, rate limiting (not implemented)
config/police/
  game.json          shared, signed terms — byte-identical with the thief's copy
  game.toml.example  template for this peer's private, uncommitted config
docs/
  PRD.md   product requirements
  PLAN.md  incremental build order
  TODO.md  active step and carried-forward work
tests/
```

`README.md` and `CLAUDE.md` stay at the repository root: the specification
(ch. 9.4.2) requires the academic report to be the root `README.md`, and
`CLAUDE.md` is read from the project root by tooling.

## Running

```
uv sync
uv run pytest --cov      # 55 tests, 99% coverage (floor: 85%)
uv run ruff check .
uv run ruff format --check .
```

## Configuration

Two files, deliberately in two formats so private settings cannot leak into
shared ones:

- **`config/police/game.json`** — the agreed rules both peers sign. Must be
  byte-identical to the thief's copy; the pre-game signature exchange refuses to
  play on any mismatch.
- **`config/police/game.toml`** — this peer's private config (ports, opponent
  URL, strategy and LLM choices). Never committed; copy
  `game.toml.example` to create it.

Never commit credentials. `.gitignore` excludes `.env`, `*token*.json`,
`*.credentials.json` and the private `game.toml`; a leaked secret stays in git
history permanently even after deletion (Appendix ג).
