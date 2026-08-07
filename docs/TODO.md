# TODO — Police Agent

## Step 1 — Project setup (done)

- [x] `uv init`, `pyproject.toml` deps (fastmcp, pytest, pytest-cov, ruff)
- [x] Ruff / pytest / coverage config (85% fail-under)
- [x] `src/police_agent/{domain,infra,peer,shared}` package skeleton
- [x] `config/police/` with shared `game.json` and private `game.toml.example`
- [x] Smoke test, `.gitignore`, README/PLAN/TODO/PRD

## Step 2 — Core game/domain rules (done)

- [x] `constants.py`: `Role`, `MoveType`, `Direction` (N/S/E/W only), `DELTAS`
- [x] `domain/board.py`: bounds, orthogonal steps, `legal_moves`,
      `barrier_targets` (own cell + 4 neighbours, per spec 3.4)
- [x] `domain/actions.py`: validated `Action` value object
- [x] `domain/own_state.py`: position, visited, barrier quota, `is_confined`
- [x] `domain/rules.py`: step ceiling, survival-threshold check
- [x] `domain/scoring.py`: scoring table + series tie rule
- [x] Split into a police-only repository (spec ch. 2.4.2, 9.4)

## Step 4 — P2P/FastMCP communication (done, built out of order)

- [x] `peer/protocol.py`: `TurnMessage` / `AuditPayload` / `ControlMessage`;
      `from_dict` rejects missing required fields, tolerates unknown ones so a
      another team's superset stays interoperable (ch. 9.4)
- [x] `infra/mcp_server.py`: this peer's own server — `PeerInboxes`,
      `build_peer_server`, `start_peer_server`, port-conflict guard
- [x] `infra/mcp_client.py`: `McpTransport` — retrying outbound calls, inbox
      polling, `drain_inboxes` for a restarted sub-game
- [x] Two-port integration test over real HTTP sockets (`@pytest.mark.slow`)
- [ ] Not done here: the runtime loop that drives the transport (step 8), and
      the config loader that supplies `my_port` / `opponent_url` — timeouts and
      URLs are constructor arguments for now

## Step 6 — Scent and belief (done)

- [x] `domain/scent.py`: `ScentField` — the mandatory pheromone mechanism, to
      ch. 4.3's update law `τ(t+1) = (1−ρ)·τ(t) + Δτ` clamped at zero. Radial
      deposit over the agreed 5×5 window, multiplicative decay once per full
      turn, `{"r,c": intensity}` snapshot. Constants come from the signed terms
      (Appendix ו table 16 marks all three *kavua*); nothing here invents one.
      Tests pin it against figure 4, figure 5 and ch. 4.4's worked example
- [x] `strategy/belief.py`: `BeliefGrid` — the Bayesian belief map of ch. 6.4.
      Flat prior, `diffuse()` predict over the agreed orthogonal move set,
      `observe_smell()` update by `1 + trust·τ`, normalise, `exclude()`,
      `as_matrix()` for the step-8 heatmap. Pairs with the existing Manhattan
      chase to give the "Bayes + Manhattan" policy the book recommends (6.3.1)
- [x] `strategy/threat.py`: `ThreatEstimate` widened to the three calls the turn
      loop makes; `absorb()` was being called without ever being declared
- [x] Wired: `peer/turn_handler.py` diffuses *then* observes (predict before
      update), `peer/runtime.py` builds both from the terms, `NullScent` and
      `strategy/scent_threat.py` retired
- [ ] `belief.smell_trust` (default 4.0) is untuned — it is the one knob that
      decides how fast a reading overwhelms the prior. Tune it against a live
      thief, not against the fake transport
- [ ] The absorbed opponent trail is not kept: the belief consumes each received
      grid directly. `ScentField.absorb`/`decay_all`/`strongest_cell` exist and
      are tested for when the step-8 GUI wants a trail layer to draw

## Step 6.5 — The verbal layer (done)

- [x] `infra/ollama.py`: one stdlib call to a local Ollama server. `stream` and
      `think` both off — Qwen3 reasons out loud by default and would spend the
      whole token ceiling doing it. Every failure raises `OllamaError`, so the
      caller has exactly one thing to catch
- [x] `strategy/talk.py`: `HintWriter` — builds the prompt, cleans the reply,
      enforces the signed `hint_max_words` cap, and falls back to a canned line
      on any failure. Default provider is `ollama` with `qwen3:4b`; the
      `[trash_talk]` block in `game.toml` is private tuning and is never signed
- [x] Wired at `peer/turn_sender.py`, which now passes the thief's last hint so
      the line can answer it. `peer/seams.py` retired — the placeholder it held
      was the whole file
- [x] Appendix ה 27 (no numeric locations on the wire) is enforced by *never
      putting a cell in the prompt*: the model is told the city, whether the
      police is closing in, and what the thief said. Coordinates are scrubbed
      from the reply as well, since a model told nothing can still invent some
- [ ] Not verified against a live model — Ollama was not running on this
      machine. Run `ollama serve` and `ollama pull qwen3:4b`, then play a match
      and read the hints back out of the log before the league
- [ ] The police never bluffs deliberately. The specification permits a
      misleading hint (ch. 4.4) and the prompt allows it, but nothing steers the
      model toward a *useful* lie — baiting the thief toward a barrier is a real
      tactic left on the table

## Step 6.5b — The bluff classifier (done)

The other half of the verbal layer: the police now *listens*. Ch. 6.4 wants the
hint in the Bayes update carrying a reliability coefficient; ch. 6.5 casts the
model as a bluff classifier. Ch. 4.4 supplies the method, and the scent is the
arbiter of it.

- [x] `strategy/hint_claim.py`: free text → a compass claim. The model answers
      one character; word-boundary keywords catch what it misses and are the
      whole reader when no model is configured. Two directions in one sentence
      claim nothing — guessing would invent evidence
- [x] `strategy/bearings.py`: `strongest_cell`, `cells_toward`, `agrees` — the
      geometry, split out so `bluff.py` is judgement alone
- [x] `strategy/bluff.py`: `BluffAnalyst` — checks each claim against the
      freshest cell of the trail that arrived with it, keeps a Laplace-smoothed
      reliability, and lets a claim move the belief only when no trail arrived
      (otherwise the same turn's evidence would count twice)
- [x] `strategy/belief.py`: `scale(cells, factor)` — the update step opened up
      for evidence that is not scent. The belief still knows nothing of compasses
- [x] Reported: `opponent_reliability` and `hint_readings` in the match summary
- [ ] **Reliability is per sub-game, not per opponent.** A thief that lies its
      way through game 1 starts game 2 with a clean slate, because the analyst is
      built fresh in `PoliceRuntime.__init__`. Carrying it across a series would
      be worth real points in the league
- [ ] Only compass claims are read. A hint naming a landmark ("by the harbour")
      is unusable because the board is abstract and nothing maps a name to a
      cell. Agreeing a landmark→region map with the thief team would open this up
- [ ] The gain (0.6) and the smoothing prior are untuned, like `smell_trust`

## Step 7 — Police strategy (done, built out of order)

- [x] `strategy/brain.py`: `PoliceBrainBase` seam + shipped `PoliceBrain`
      (minimise Manhattan distance, tie-break toward unvisited)
- [x] `strategy/barrier.py`: deterministic placement — wall any reachable step
      that takes an escape from the believed thief, never when it would confine
      the police (3.4)
- [x] `strategy/threat.py`: `ThreatEstimate` Protocol + `PointThreat` /
      `UniformThreat` stand-ins until the belief map lands
- [x] `strategy/__init__.py`: `resolve_brain` reading `strategy.police_class`
- [ ] Re-tune once step 6 supplies a real `BeliefGrid` — the stand-in estimates
      are certain in a way a real belief never is, which flatters the heuristic

## Step 3 / 8 — Runtime peer process (done, built out of order)

- [x] `shared/config.py` + `shared/schema.py`: load the agreed `game.json` and
      the private `game.toml`, dotted access. The agreed file is overlaid *on
      top of* the private one so a peer cannot sign one board and play another
- [x] `peer/terms.py`: the must-match subset, validated before a port is opened
- [x] `peer/handshake.py`: mutual signed-terms exchange (`Negotiation`)
- [x] `peer/runtime.py`: `PoliceRuntime` — negotiate → wait → fold in → decide
      and send → audit. The thief opens, so the police waits first
- [x] `peer/turn_handler.py` / `peer/turn_sender.py` / `peer/sealing.py`
- [x] `peer/summary.py`: audit exchange; a forged opponent log forfeits
- [x] `domain/crypto.py`: SHA-256 commit-reveal (partial step 5 — see below)
- [x] `__main__.py`: `police-agent` CLI (`--port`, `--opponent`, `--summary`)
- [x] `tests/peer/fake_transport.py`: scripted thief double, same six-method
      surface as `McpTransport`; plus a live two-port match in `tests/infra/`

## SDK architecture (done)

The submission guidelines require all business logic to be reachable through an
SDK layer, with front ends delegating to it and holding none themselves. The CLI
was the counter-example: it loaded the config, resolved the port, started the
server, built the transport and constructed the runtime.

- [x] `sdk/options.py`: `MatchOptions` — what a caller may choose about a match
- [x] `sdk/agent.py`: `PoliceAgentSDK` — load terms, open the mailbox, play,
      save the record. Lazy and idempotent, so reading `agent.port` binds no
      socket and `connect()` twice opens one server. Config and transport are
      injectable, which is what lets a match be played against
      `tests/peer/fake_transport.py` with no sockets and no opponent process
- [x] `__main__.py` reduced to flags in, lines out, exit code
- [x] `police_agent.PoliceAgentSDK` re-exported lazily from the package root, so
      `import police_agent` still costs nothing for a test that wants a board
- [x] Wire deadlines now come from the agreed terms
      (`network.watchdog_timeout_seconds` / `response_timeout_seconds`). The CLI
      built `McpTransport` with neither, so both peers silently used the
      constructor's 60 s/30 s regardless of what they had signed
- [ ] The step-8 GUI and replay viewer must be built as front ends over this
      object, not beside it. `listener=` is already the progress seam

## Step 8 — GUI and replay (done; reporting still open)

Adapted from the course reference's `gui/` package. The structure was taken —
shared window chrome over a board canvas, a live app mirroring an event stream
from a worker thread, a replay player feeding a log back through the pure
domain. The code was rewritten: our runtime publishes different events, our
config names different things, and every reference file carries an
"all rights reserved / Educational Use EULA" header, so copying one into a
public repository would be redistribution.

- [x] `peer/view.py`: `snapshot(runtime)` — everything mutable copied at the
      moment the event fires. The game plays on a worker thread while Tk redraws
      on the main one, so a view holding a live `state.visited` would be iterated
      while the game was still adding to it. Skipped entirely when no listener is
      attached, so the headless agent builds no belief matrix it will not draw
- [x] `peer/controls.py`: `GameControls` — pause/play/stop as `threading.Event`s,
      checked by `runtime._turn_loop` at the **turn boundary**. A pause landing
      between sealing a move and sending it would leave this peer committed to
      something the opponent never received. New result `ABORTED`, and it skips
      the audit for the same reason `TECHNICAL_LOSS` does
- [x] `gui/palette.py` + `board_view.py`: the mandatory heatmap. Colour scales
      against the *current peak*, not an absolute — a belief over 49 cells starts
      at 0.02 and rarely passes 0.3, so an absolute scale would draw every
      interesting state as a uniform white
- [x] `gui/window.py`: chrome shared by both views, so a replay screenshot is
      evidence about the live run (ch. 9.4.2 asks for both)
- [x] `gui/game_mode.py`: the Table-22 verbal-game mode and model label
- [x] `gui/live_apply.py` / `live_controls.py` / `player.py`: the live app
- [x] `gui/replay_data.py` / `replay_controls.py` / `replay.py`: the Visual
      Replay Player. The belief is **recomputed** from the recorded scent grids
      and each commit re-verified as it is drawn, rather than reading
      `audit.passed` back out of the same file a forger would have edited
- [x] `--gui` and `--replay` on the CLI; `sdk.load_summary`; the SDK's `listener`
      and `controls` made settable, since the window needs an SDK to build itself
      from before it has a window to steer with
- [x] Both windows built, driven and closed cleanly against real Tk
- [ ] **Screenshots for the report (ch. 9.4.2) are not taken.** Needs a live
      match against the thief peer, not a scripted log
- [x] **The mandatory Gmail report.** Built in step 9 below
- [ ] **Replay cannot show the hints this peer sent.** They are nowhere in the
      summary — the sealed payload is the peer's *truth* and a taunt is not, and
      the wire message is not logged. Live play shows them because the `moved`
      event carries one. Recording them would make the log complete
- [ ] **No sub-game selector.** The naming convention now exists (step 9's
      `report/writer.py` writes `log_<game_id>_gNN.json` and discovers siblings),
      but nothing in the replay window offers a list of them. A series driver is
      still the prerequisite, not the widget
- [ ] **No bidirectional control channel.** The reference lets one peer ask the
      other to restart a series. `ControlMessage` and `McpTransport.poll_control`
      already exist here and the runtime ignores both; the opponent would have to
      agree to honour it, which is a cross-repo conversation

## Step 5b — Gatekeeper, token accounting, public tunnelling (done)

Three mandatory Appendix He rules with nothing behind them: the five
`rate_limiter_gatekeeper` values sat signed in `game.json` unread (rules 28/29),
no summary field reported model token spend (rule 54), and this peer could only
ever play an opponent on `127.0.0.1` (rule 10, ch. 2.4).

- [x] `shared/rate_limit.py`: `TokenBucket` (continuous refill) and
      `DosDetector` (sliding-window anomaly, latches once tripped) — the two
      measuring instruments, deciding nothing themselves
- [x] `shared/admission.py`: `AdmissionQueue` — strict FIFO waiting line over the
      bucket and a concurrency cap; only the configured depth is a hard refusal,
      everything shorter queues rather than drops (the scorecard's "overload is
      queued, not dropped or crashed")
- [x] `shared/gatekeeper.py`: `Gatekeeper` — the policy built from both:
      DOS check → queue → bucket → retry/backoff, with counters for the report.
      **Scoped to outbound calls to a third party only.** The peer-to-peer MCP
      transport is deliberately excluded and calls out directly
      (`infra/mcp_client.py`): those are our own turns, there is no 429 waiting
      on the other end, and throttling them would trade a technical loss on the
      opponent's watchdog for a protection nobody asked for
- [x] The inbound half is the opposite policy on the same instrument
      (`peer/runtime.py._turn_loop`): every incoming message is counted by a
      second `DosDetector`, but a tripped reading only ever reaches the summary
      (`inbound_dos`) — a peer that dropped a turn to defend against a suspected
      flood would forfeit the very match it was defending
- [x] `shared/tokens.py`: `Usage` / `TokenLedger` — counts only what Ollama's own
      reply reports (`prompt_eval_count`/`eval_count`), never estimated. Threaded
      through the existing `ask(prompt, system) -> str` seam
      (`infra/ollama.py`, `strategy/talk.py`, `strategy/bluff.py`) without
      changing it: a plain two-argument stand-in is still a valid asker and
      simply consumes nothing, so no test injection site needed updating
- [x] One `Gatekeeper` and one `TokenLedger` built per `PoliceRuntime`, shared by
      both halves of the verbal layer (hint-writing and hint-reading) — two
      gates would let through twice the agreed rate
- [x] `peer/summary.py`: `tokens`, `gatekeeper`, `inbound_dos` blocks in the
      match record
- [x] `infra/tunnel.py` + `infra/ngrok_agent.py`: wraps `ngrok` as a subprocess,
      opt-in behind `--tunnel` so the local/two-peers-on-one-machine default is
      unaffected. The authtoken is never read, stored or logged — ngrok supplies
      it from its own config (`ngrok config add-authtoken`, run once by the
      user). A reserved static domain is private config (`game.toml`, not the
      signed `game.json`); the public URL is read back from ngrok's local agent
      API, never parsed from its terminal output
- [x] `sdk/agent.py`: `tunnel_domain` / `public_url` properties; `connect()`
      opens the tunnel *after* the server binds, so an opponent already dialling
      a reserved domain is never refused by a port nothing is listening on yet
- [x] Verified end to end against real ngrok (unauthenticated case): the exact
      "run `ngrok config add-authtoken`" message, correct exit code, no traceback
- [ ] **Not yet verified against an authenticated tunnel on a reserved domain.**
      Needs the account's authtoken configured on the machine that runs the
      league match
- [ ] **`max_retries` is a ceiling, not a quota** — a call's `budget` (seconds)
      can cut it short before the ceiling is reached, deliberately, so a taunt
      sharing its turn with the opponent's watchdog gives up rather than keeps
      trying. Worth restating in the report: it satisfies rule 28's *minimum*,
      not a promise to always retry that many times
- [x] **Quota manager (daily counter).** Ch. 9.3.1's first gate, built in step 9
      below as `shared/quota.py` and spent by the Gatekeeper ahead of everything
      else. Optional, so the Ollama path is unaffected
- [x] **The series token total.** Still absent from the per-sub-game summary, and
      deliberately: a sub-game runs in its own process and cannot see its
      siblings' spend. Step 9's result artifact adds it up from the filed records
      instead (`tokens_used.total`), which is computing it rather than inventing it
- [ ] **A free ngrok account allows one tunnel at a time.** Both peers cannot
      tunnel from the same machine; the error message says so and how to clear
      it (`pkill -f 'ngrok http'` or the ngrok dashboard)
- [ ] **`--tunnel --gui` opens the tunnel but the window does not show the
      public URL.** It is only printed on the headless path today

## Step 9 — Step-zero declaration and the reporting chain (done)

Four mandatory Appendix ה rules with no code at all: the signed hardware
declaration (24), the commit hash of the code played (53), the Gmail report of a
mandatory JSON as an attachment under a send-only scope (30/32/34/51), and the
daily quota ahead of the token bucket (28). Rule 35's sanction for a missing
report is nought for **both** teams, so this was the most expensive gap open.

- [x] `infra/hardware.py`: an eight-field machine spec, cached per process.
      Every probe may fail and none may raise — a figure that cannot be measured
      is the literal `"unknown"`, because the declaration is signed and an
      invented number in it would be a false statement we stand behind
- [x] `infra/gitcommit.py`: `commit_hash(config)` / `working_tree_dirty()`.
      `rev-parse HEAD` so a detached checkout still answers; a configured
      `game.github_commit` wins, for running from a build with no `.git`. The
      dirty flag is its own boolean, not a `-dirty` suffix, so the hash stays
      something the grader can check out
- [x] `peer/step_zero.py`: rules 24 and 53 as one sealed record (ch. 5.5), built
      in `PoliceRuntime.__init__` at `records[0]`, its digest published in the
      handshake identity before the first move and its nonce revealed only at the
      audit. A tampered declaration fails the log audit as step 0
- [x] `report/`: `ids.py` (the shared `game_id`/`game_uid` and the **two**
      non-interchangeable canonical hash forms), `facts.py`, `declaration.py`,
      `artifacts.py` (config + log), `result.py`, `writer.py`
- [x] `shared/quota.py`: `DailyQuota` — persisted across processes, spent by the
      Gatekeeper before the DOS check. Optional, so Ollama is unaffected
- [x] `infra/gmail.py` + `gmail_client.py`: `gmail.send` and nothing wider, the
      report as an `application/json` attachment, Google's libraries an optional
      extra imported lazily. `enabled = false` and `mode = "draft"` by default,
      and a "draft" is a local `.eml` file — `gmail.send` cannot create a Gmail one
- [x] `--report` / `--report-dir` on the CLI, `write_artifacts` and
      `email_report` on the SDK, `[email]` documented in `game.toml.example`
- [x] `.gitignore` bug fixed: `*.credentials.json` never matched a bare
      `credentials.json`, so the file Appendix א tells you to download was not
      actually ignored
- [ ] **The live send has never run against Google.** Everything offline is
      exercised; the send path is proven against a stand-in for the client
      library. Run it once, deliberately, before the league
- [ ] **No series driver.** `--report` writes a result over whatever sub-games
      are filed, but nothing plays a series: each sub-game is still started by
      hand with `game.sub_game_number` set in `game.toml`
- [ ] **The opponent's declaration is not audited.** Its step-zero record arrives
      in the reveal and its hash is re-verified like any other, but nothing
      checks that the hardware it declared is plausible or that the commit it
      names exists. Part of the same semantic audit step 5 still owes

## Step 3 — Local playable simulation (superseded)

Overtaken by the runtime above: the scripted match driver this step called for
is `tests/peer/fake_transport.py`, and it drives the real `PoliceRuntime`
rather than a separate simulation path.

- [ ] Load `config/police/game.json` into the domain layer
- [ ] Test double standing in for the thief (test scaffolding only — never
      shipped agent code, and never an in-process opponent at runtime)
- [ ] Scripted match driver; random/scripted move choice only, since real
      strategy is step 7

## Carried forward

- [ ] **Cross-repo — the thief does not concede a barrier capture.** When a
      police barrier traps the thief (Appendix ה 46/47), the thief's runtime
      sets its own result to `capture` but sends its terminal message with
      `claim_response = None`. The police only registers a win on
      `claim_response.caught`, so it keeps playing, times out, and records
      `technical_loss`. Both peers name the police as winner, but the two
      `result` strings disagree. Fix belongs in the **thief repo** (send
      `{"caught": true}` on that path); settle it before the league match.
- [ ] **Cross-repo — timeout asymmetry.** The thief waits 30 s for the audit
      reveal; this peer's turn timeout falls back to 60 s, and to **180 s** if
      `game.toml` is copied unchanged from the example. The thief will walk away
      before the police notices it has gone. Agree one number.
- [ ] **Cross-repo — the scent model must be locked before the series.** Appendix
      ה 23 makes this a condition of the game being valid at all ("deviation in
      the decay formula voids the game"), and ch. 4.5 asks the two groups to
      agree the emission/decay model in full and hash it. `domain/scent.py`
      follows the **book**, and reproduces all four of its published numbers
      (figure 4's window, figure 5's curve, ch. 4.4's `0.81`, and the stated
      `[0, 0.9]` range). The course **reference implementation does not**, in
      three places — so an opponent who copied it will compute a different
      field, and this is the conversation to have before the league:
      | | Ours (the book) | Reference |
      |---|---|---|
      | Decay | `(1−ρ)·v`, still ≈0.11 at t=20 | `v − 0.10`, gone by t=9 |
      | Falloff | radial 0.90/0.62/0.42/0.20/0.14/0.04 | Chebyshev rings 0.9/0.6/0.3 |
      | Order | decay then deposit → centre goes out at `0.9` | deposit then decay → `0.8` |
      The three *values* (0.9, 0.10, 5×5) are Appendix ו table 16 fixed
      constants and are identical either way; only the formulas differ.
- [ ] **Two readings the book does not settle**, both decided in `domain/scent.py`
      and worth putting in the agreement explicitly rather than leaving implicit:
      the falloff *curve* (a Gaussian at σ=1.15 is what reproduces figure 4, but
      ch. 4.5 leaves the curve to the two groups), and whether `+ Δτ` means
      accumulate or refresh (we refresh — ch. 4.4's `0.81` only holds that way,
      and it is what makes the stated `[0, 0.9]` range hold without a clamp).
- [ ] **Cross-repo — the thief still hardcodes `smell_grid={}`.** This peer now
      broadcasts a real decaying field, so the police's belief map is fed, but
      the thief's is not and it must fall back on its prior. Until that side
      emits too, a match is still not a symmetric test of strategy. Fix belongs
      in the **thief repo**.
- [ ] **Step 5 is only half done.** Sealing, the handshake signature and the
      hash re-verification of the opponent's revealed log all work. What is
      still missing is the *semantic* audit: re-checking the thief's capture
      answers and survival claim against its revealed positions. `audit_records`
      proves the log was not rewritten; it does not yet prove the log is
      consistent with what the thief claimed during play.
- [x] **Anti-replay on incoming turns** (`peer/turn_handler.py`). Every turn is
      identified by its commit and remembered; a repeat is dropped before it
      touches state, and `peer/runtime.py` does not answer one. The commit is
      keyed on rather than a `(step, commit)` pair because the step sits *inside*
      the sealed payload, so rewriting it on the wire cannot launder a spent
      turn. Dropped rather than forfeited: `McpTransport` retries, so a repeat
      is at least as likely to be our own network as an opponent.
- [ ] **Specification ambiguity — Appendix ה 46.** The barrier policy never
      walls the cell it *believes* the thief occupies, even though a barrier
      there is a capture condition: the specification does not pin down how that
      is evaluated against a sealed, simultaneous move. Stepping onto the cell is
      a capture attempt that costs no quota, so the ambiguous option is never the
      only one available. Resolve the timing with the other group before the
      interoperability test, then revisit `strategy/barrier.py`.
- [ ] **`_send_with_retry` catches bare `Exception`** — a genuine bug such as a
      misspelled tool name retries for the full connect budget before surfacing
      as a `TransportError`. Narrow it once the runtime loop exercises the path.

- [ ] **Step 5 — audit verification.** The thief-side capture rules (Appendix ה
      46/47) were removed from `domain/rules.py` because the police cannot
      compute them during play. The police still owes their *verification*:
      once the thief reveals its sealed log, re-check every capture-claim
      answer, every barrier-capture report and any confinement claim against
      the revealed positions. Operates on the opponent's revealed records, not
      on `OwnGameState`.
- [x] Companion **thief repository** created and cross-linked from `README.md`:
      https://github.com/Moaawiyah/Ai_thief (public, so accessible to the grader).
- [ ] Add the reverse cross-link in the **thief repo's** README, pointing back to
      https://github.com/Moaawiyah/police-agent — ch. 9.4 requires the link in
      *both* directions. Done in that repo, not this one.
- [ ] Merge the feature branch into the main branch (Appendix ג).
