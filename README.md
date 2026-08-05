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
- **Whose vocabulary wins.** Both peers compare the agreed-terms dict for exact
  equality, so a term one side signs and the other does not fails the handshake
  even when every shared value agrees — and a peer always agrees with itself, so
  no local test catches it. The signed key set is therefore copied verbatim from
  the course reference rather than designed, and pinned by a test
  (`tests/peer/test_terms_contract.py`). `survival_threshold` is consequently
  *not* signed: the reference does not sign it, so neither may we.

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
_Pending — the windows exist and run (`--gui`, `--replay`); the screenshots
themselves are taken from a live league match against the thief peer._

### 6. Companion repository link
Thief agent: **https://github.com/Moaawiyah/Ai_thief**

---

## Current status

**The police agent plays a complete sub-game.** Handshake, turn loop, sealed
moves and the end-of-game audit all work over real MCP sockets against a
separate process.

One operational check remains before a league match:
- **The Gmail send path has never run against Google.** The whole reporting
  chain is built and tested (`--report`, below), but only the offline half has
  been exercised for real: the default writes a local `.eml` draft, and the
  live send is proven against a stand-in for Google's client library rather
  than against Google. Run it once, deliberately, before the league.

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
uv run police-agent --report                 # write the four report artifacts
uv run police-agent --gui                    # play with the live board window
uv run police-agent --tunnel                 # publish a public URL
uv run police-agent --league --tunnel        # enforce the league tunnel profile
```

The thief must be started from its own repository, as a separate process.

## Playing over the public internet

Two peers on two different machines both sit behind NAT, so `127.0.0.1` in
`network.opponent_url` cannot describe either of them (spec ch. 2.4, Appendix
He rule 10). `--tunnel` wraps [ngrok](https://ngrok.com) as a subprocess and
publishes this peer's MCP server on a public URL:

```
ngrok config add-authtoken <your token>      # once, in your own terminal
uv run police-agent --tunnel
```

The authtoken never touches this code or this repository — ngrok keeps it in
its own config file. The printed URL is what goes in the *opposing* team's
`network.opponent_url`. Without a reserved domain the URL is different on
every restart, which is fine for a one-off test but breaks a series the
opponent has already configured against you; reserve one at
[dashboard.ngrok.com/domains](https://dashboard.ngrok.com/domains) and set
`network.tunnel_domain` in your private `game.toml` to keep the same address
across restarts. See `config/police/game.toml.example` for the exact key.

`--league` is intentionally stricter than `--tunnel`: it requires a configured
reserved domain, an HTTPS public opponent URL (never localhost or a private IP),
and uses only the signed watchdog/response deadlines. Gmail reporting remains
optional. Local practice mode keeps working without either flag.

## Thief integration contract

The thief repository is not modified here, but its audit implementation must
reveal one sealed record for each accepted turn. Each record must expose the
same committed `step`, `position`, and `move` sent under that turn's `commit`.
Steps are contiguous from 1; moves are one legal orthogonal move or `HOLD:-`.
It must echo the exact police `capture_claim` in its next `claim_response`,
report `caught` truthfully from its revealed prior position, and stop after a
capture. A valid police barrier on the revealed thief cell, or one that leaves
the thief no legal move, is a police capture even if the thief reports another
outcome. League runs on that side must apply the same public HTTPS tunnel and
signed-timeout requirements.

## The Gatekeeper and token accounting

Every outbound call this peer makes to somebody else's service — today that
is the local Ollama model behind the verbal layer — goes through one gate
(`shared/gatekeeper.py`): a token-bucket rate limiter, a bounded FIFO queue so
overload waits its turn instead of being dropped, retry with backoff, and a
DOS circuit-breaker that locks the door if this process's own outbound rate
runs ten times past the agreed limit (Appendix He rules 28/29). The five
limits — requests/minute, concurrency, backoff, retries, queue depth — are
already signed into `config/police/game.json` under
`rate_limiter_gatekeeper`; a term the agreed file does not name falls back to
the Appendix Vav example value, per its "minimum" status.

The peer-to-peer MCP transport deliberately does **not** go through the gate:
those are our own turns to the opponent, not requests against a third party's
quota, and throttling them would trade a technical loss on the opponent's
watchdog for a protection nobody asked for. An inbound flood detector on the
turn loop watches the *opponent's* message rate instead, but only ever
reports it — dropping a legal turn to defend against a suspected flood would
forfeit the match to the very peer under suspicion.

Every model call's real cost — Ollama's own `prompt_eval_count` /
`eval_count`, never estimated — lands in a per-match ledger and is reported in
the summary (`tokens`), alongside the gate's own counters (`gatekeeper`) and
the inbound reading (`inbound_dos`), so the end-of-game JSON shows the rate
limiter was actually in the path, not merely present in the config (Appendix
He rule 54).

## The step-zero declaration and the mandatory report

### Before the first move

Appendix He rule 24 requires a signed hardware declaration and rule 53 the
commit hash of the code being played. Ch. 5.5 makes them one object: a
"step-zero" record, built *before* the first move, carrying the machine spec,
the code version, the commit, the group and the sub-game number.

The chapter's point is that the declaration must be unforgeable in retrospect.
Writing the specs into a report at the end would not be — by then the match is
over and a peer that lost could describe whatever hardware flattered it. So the
declaration is sealed under the same commit-reveal this repository already uses
for turns (`peer/step_zero.py`), its digest is handed to the opponent during the
handshake, and its nonce is not revealed until the end-of-game audit. It rides
at `records[0]`, so a tampered declaration fails the log audit as step 0 like
any other rewritten record.

Every probe is best effort and none of them raises (`infra/hardware.py`,
`infra/gitcommit.py`). A figure that cannot be measured is the literal
`"unknown"`, never a guess: the declaration is signed, and an invented number in
it would be a false statement this peer cryptographically stands behind. A dirty
working tree is reported as its own boolean beside the hash rather than as a
`-dirty` suffix, so `github_commit` stays something the grader can check out.

### The four artifacts

`--report` writes ch. 9.3.3's four JSON files under
`logs/<your group id>/`, every filename derived from the `game_id` so files from
two matches can never be mixed, and all four carrying one `game_uid`:

```
declaration_<game_id>.json      what holds across the whole series
config_<game_id>_gNN.json       the agreed physics and scoring, hashed
log_<game_id>_gNN.json          every sealed record, for the replay simulator
result_<game_id>.json           the binding one, mailed to the lecturer
```

A fifth file, `record_<game_id>_gNN.json`, is the raw match record. It is not a
schema artifact and `links` does not mention it: the result must cover *every*
sub-game while a sub-game runs in its own process, so each run files its record
and a later run picks its siblings up from there.

### Mailing it

Rule 32 has each team send the report itself, and rule 35 attaches the sanction:
if either report is missing, **neither** team scores for the match, however the
board went. Rule 34 fixes the form — structured, machine-readable JSON as an
attached file. The body here says where the report is and carries no game data.

Off by default. `email.enabled = false` and `email.mode = "draft"` in
`game.toml`, and both have to be changed deliberately before anything leaves the
machine. Google's libraries are an optional extra (`uv pip install
'police-agent[gmail]'`) imported lazily, so a default run needs no Google
account, no `credentials.json` and no network at all.

Every real send crosses ch. 9.3.1's gates: a daily quota (`shared/quota.py`,
persisted so a series of sub-games in separate processes cannot each believe it
is the first), then the token bucket, then the anomaly detector. The mail gate is
a separate `Gatekeeper` from the runtime's — figure 13's gates protect a
*provider's* allowance, and Ollama's rate window is not Google's.

### Where we deviate from the specification, and why

1. **"Signed with a pre-supplied key" (ch. 5.5) vs. a keyless SHA-256.** The
   course reference's per-group `signature` is a plain hash of the block, so
   anybody who can recompute it can forge it. We emit that field for interop
   with the opposing team's parser, and satisfy the chapter separately through
   commit-reveal: the same declaration sealed, its digest published at the
   handshake, its nonce withheld until the audit. That is a real
   non-retroactive-forgery property, with no PKI the course never issues.
2. **`gmail.send` cannot create a Gmail draft.** `users.drafts.create` needs
   `gmail.compose`, a broader grant than rule 30 and Appendix Alef step Gimel
   allow. So `mode = "draft"` writes a local `.eml` file. Rule 30 wins.
3. **Appendix Alef's sample mails a free-text body; rule 34 forbids one.** The
   report is an attachment and the body carries no game data. The rule wins.
4. **Hardware: five fields in ch. 5.5, six in the reference block, eight
   internally.** The artifact publishes the reference's six (`gpu_type` →
   `gpu_model`); all eight stay in the sealed payload, which is where ch. 5.5's
   requirement actually has to be met and where no foreign parser can object.
5. **`mutual_agreement.sha256` is symmetric in the result and asymmetric in the
   log.** The log's is over *this* peer's own records — it is one peer's
   testimony, and a digest matching the opponent's would mean we had hashed
   something other than what we are testifying to. Only `confirmed` is
   comparable there. The result's covers the agreed outcome and both peers must
   land on it. This looks like a bug; it is stated in both files' `_remark`.
6. **The opponent's token spend is always `0`.** No peer can measure another's,
   and an estimate would be a number nobody could check. It is excluded from the
   symmetric digest so an honest zero can never cause a disagreement.
7. **`config_sha256` is over the whole agreed `game.json`, not the handshake
   subset.** `peer/terms.py` compares a subset on the wire on purpose (a term
   the opponent's build does not know would fail every negotiation), but ch. 9.2
   loads the agreed file byte-identically on both sides precisely so it can be
   hashed consistently, and the lecturer compares files rather than handshakes.
8. **Three unrelated `schema_version`s** — `game.json` 1.2, `game.toml` 1.10,
   the artifacts 1.1. The artifact literal versions the artifact, not us.

## The windows

Two of them, over the same board canvas, because a screenshot of one is only
evidence about the other if they draw the same thing (spec ch. 9.4.2 asks for
both). Adapted from the course reference implementation's `gui/` package — the
structure was taken, the code was rewritten.

**Live** (`--gui`) shows this peer playing: its true position, its trail, the
declared barriers, and the belief heatmap over where the thief might be. The
window opens idle so both peers can be started before a match begins; Start
negotiates and plays, Pause/Play/Stop steer *this* peer only. What it cannot
show is the thief — its position is not in this process to draw (ch. 2.4.2), and
the red cloud is the whole answer.

**Replay** opens a saved match log:

```
uv run police-agent --replay result.json
uv run police-agent --replay result.json --opponent-log thief-result.json
```

Play/pause, single-step, jump to a step. The belief map is *recomputed* from the
recorded scent grids by the same `BeliefGrid` the agent played with, and each
step's SHA-256 commit is re-verified as it is drawn — so `verified OK` under the
board is being proven in front of the viewer rather than read back out of the
same file. Edit a payload in the log and the step turns `TAMPERED`. With the
thief's revealed log supplied, both true positions are drawn: unknowable during
play, plain history once both peers have revealed.

Pausing is a real cost, and the banner says so. There is no referee holding the
game while this peer thinks: the thief's watchdog keeps running, and a long
enough pause is a technical loss.

## Layout

```
src/police_agent/
  constants.py  roles, action types, the four legal directions
  exceptions.py the deliberate-error hierarchy (a crash is a technical loss)
  __main__.py   the `police-agent` CLI: a front end, no game logic of its own
  sdk/          the public API every front end goes through (see below)
  gui/          the live board window and the Visual Replay Player
  domain/       board geometry, actions, own state, rules, scoring, commit-reveal
  strategy/     the police brain: chase heuristic, barrier policy, threat estimate
  infra/        FastMCP server (my mailbox), client (the opponent's URL), the
                ngrok tunnel (tunnel.py + ngrok_agent.py), the Gmail reporter
                (gmail.py + gmail_client.py), the hardware and commit probes
  peer/         the runtime: handshake, turn loop, sealing, audit, wire protocol,
                the sealed step-zero declaration
  report/       the four mandatory JSON artifacts (ch. 9.3.3) and their writer
  shared/       config loading, version, the API Gatekeeper, the daily quota and
                the token ledger
config/police/
  game.json          shared, signed terms — byte-identical with the thief's copy
  game.toml.example  template for this peer's private, uncommitted config
docs/
  PRD.md   product requirements
  PLAN.md  incremental build order
  TODO.md  active step and carried-forward work
tests/
```

### The SDK layer

Every capability of this agent is reachable through one object,
`police_agent.sdk.PoliceAgentSDK`. Front ends parse their own input and render
what comes back; they do not load a config, resolve a port, build a transport or
construct a runtime. The `police-agent` CLI is the first such front end and the
step-8 GUI and replay viewer will be the next — one composition root rather than
three that drift apart the first time a constructor changes.

```python
from police_agent.sdk import MatchOptions, PoliceAgentSDK

agent = PoliceAgentSDK(MatchOptions(port=8801, opponent_url="http://127.0.0.1:8802/mcp"))
agent.connect()  # my mailbox opens, the opponent's URL is dialled
summary = agent.play()  # one sub-game, to a result
agent.save_summary(summary, "result.json")

paths = agent.write_artifacts(summary)  # the four mandatory JSON artifacts
agent.email_report(paths)  # None unless [email] switches it on
```

The layer holds no game rules. It decides *which* objects are built and with
what settings; how the game is played stays in `domain/` and `peer/`. Both the
transport and the config can be injected, which is what lets a whole match be
played against a test double with no sockets and no opponent process.

`README.md` and `CLAUDE.md` stay at the repository root: the specification
(ch. 9.4.2) requires the academic report to be the root `README.md`, and
`CLAUDE.md` is read from the project root by tooling.

## Running

```
uv sync
uv run pytest --cov              # 798 tests, 100% coverage (floor: 85%)
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
  URL, reserved ngrok domain, strategy and LLM choices, and the `[email]` block:
  the recipient, the send mode, the credential paths and the daily cap). Never
  committed; copy `game.toml.example` to create it.

The `[email]` settings stay private deliberately. The recipient, the paths and
the daily limit are this peer's own, no opponent verifies them, and adding a key
to the signed `game.json` would break byte-identity with the thief's copy.

Never commit credentials. `.gitignore` excludes `.env`, the private `game.toml`,
and both halves of the Gmail OAuth pair by the exact names Appendix א has you
download them under — `credentials.json` and `token.json` literally, because
`*.credentials.json` does not match a bare `credentials.json`. A leaked secret
stays in git history permanently even after deletion (Appendix ג).
