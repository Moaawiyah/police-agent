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
Each peer hosts its own FastMCP server and knows exactly one thing about its
opponent: a URL. Four dilemmas the orchestration had to settle:

- **Who waits for whom.** Two independently launched processes never start
  together, so a refused connection in the opening seconds is the expected case,
  not an error. Outbound calls retry until a deadline; only then is it a
  `TransportError`.
- **Where the turn token lives.** There is no referee to hold one, so receiving
  a `TurnMessage` *is* the hand-over. The message is the token.
- **Serving vs. playing.** MCP tools run on server worker threads while the game
  loop is single-threaded. The tools therefore do no reasoning at all — they drop
  the raw payload into a queue and return, so a slow strategy can never stall the
  opponent's HTTP call.
- **Trusting a claim you cannot check.** The thief reports its own capture and
  survival; the police can verify neither during play. Survival is checked
  against the agreed threshold immediately and disputed if premature; the rest
  waits for the audit, where a log that will not hash forfeits the game outright.

### 3. Strategies implemented
_Partial — the shipped heuristic exists (step 7); it will be re-tuned once the
belief map (step 6) replaces the placeholder threat estimate._

- **Chase.** Minimise Manhattan distance to the believed thief cell — the true
  remaining move count once diagonals are illegal — breaking ties toward
  unvisited cells, which the scoring table credits.
- **Barrier.** A barrier costs a fixed quota slot *and* that turn's step, so it
  is placed only when it provably corners: the believed thief within reach, the
  wall landing on one of its own legal steps, and at most one escape left after
  it. Placements that would leave the police itself with no legal step are
  rejected outright (spec 3.4).
- **Determinism.** No random draw sits in the move path. Moves are sealed and
  re-checked against the revealed logs in the end-of-game audit, so a decision
  that turned on a coin flip could not be recomputed from a replayed log.

### 4. Learning curves
_Not applicable unless a reinforcement-learning agent is trained._

### 5. Screenshots
_Pending — requires the live GUI belief map and the Replay App showing
`Verified OK` (step 8)._

### 6. Companion repository link
Thief agent: **https://github.com/Moaawiyah/Ai_thief**

---

## Current status

**The police agent plays a complete sub-game.** Handshake, turn loop, sealed
moves and the end-of-game audit all work over real MCP sockets against a
separate process.

Two gaps are open and both matter before a league match:

- **Scent emission is a no-op.** The police broadcasts an empty `smell_grid`,
  so an opponent receives no signal from it. The match completes correctly; it
  is not yet a fair contest. Step 6.
- **The audit checks hashes, not meaning.** A rewritten opponent log is caught.
  A log that hashes correctly but contradicts the claims made during play is
  not yet re-checked. Step 5, partially done.

See [docs/PLAN.md](docs/PLAN.md) for the build order, [docs/TODO.md](docs/TODO.md)
for what is carried forward, and [docs/PRD.md](docs/PRD.md) for the product
requirements.

## Running a match

Both peers are separate processes. Copy `game.toml.example` to `game.toml`, set
`network.my_port` and `network.opponent_url`, then:

```
uv run police-agent                          # uses config/police/game.toml
uv run police-agent --port 8801 --opponent http://127.0.0.1:8802/mcp
uv run police-agent --summary result.json    # also write the match record
```

The thief must be started from its own repository, as a separate process.

## Layout

```
src/police_agent/
  constants.py  roles, action types, the four legal directions
  exceptions.py the deliberate-error hierarchy (a crash is a technical loss)
  __main__.py   the `police-agent` CLI: start my server, play one sub-game
  domain/       board geometry, actions, own state, rules, scoring, commit-reveal
  strategy/     the police brain: chase heuristic, barrier policy, threat estimate
  infra/        FastMCP server (my mailbox) and client (the opponent's URL)
  peer/         the runtime: handshake, turn loop, sealing, audit, wire protocol
  shared/       config loading (rate limiting not implemented)
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
uv run pytest --cov              # 229 tests, 99% coverage (floor: 85%)
uv run pytest -m "not slow"      # skip the tests that bind real sockets
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
