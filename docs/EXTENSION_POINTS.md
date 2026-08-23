# Extension points

Where this agent is meant to be extended, and what contract each seam holds you
to. Every point below is reachable without editing shipped code: by
configuration, by subclassing a published base, or by satisfying a `Protocol`.

The rule behind all of them is the same one `sdk/__init__.py` states: a front
end or an extension talks to a published seam, never to `peer/` or `domain/`
internals. That is what keeps a replaced part from corrupting a game the rules
engine is supposed to arbitrate.

## 1. The move policy (`strategy.police_class`)

The primary seam. Point `[strategy] police_class` in `config/police/game.toml`
at a dotted `"package.module:ClassName"` and that class runs instead of the
shipped `PoliceBrain`:

```toml
[strategy]
police_class = "my_team.strategy:MyPoliceBrain"
```

Subclass `PoliceBrainBase` (`strategy/brain.py:39`) and override one of two
hooks, depending on how much you want to replace:

| Hook | Scope | Use when |
|---|---|---|
| `_pick_move(moves, state, threat)` | chooses among legal single steps | you want a different chase, same barrier policy |
| `_decide_move(state, threat, barriers_max)` | the whole turn, BARRIER included | you want to change when walls are spent |

Contract: `moves` is never empty when `_pick_move` is called, and every
candidate already came from `Board.legal_moves`, so whatever you return is
accepted by `OwnGameState.apply_move`. A brain cannot produce an illegal move —
it can only lose the game. Take the `rng` the runtime hands you rather than
seeding your own, or a saved seed stops reproducing its game
(`strategy/brain.py:49`).

Resolution and validation live in `strategy/__init__.py:40` — a typo raises
rather than silently falling back, because a game played with the wrong brain
looks like it ran correctly.

## 2. The threat estimate (`ThreatEstimate` protocol)

`strategy/threat.py:24` defines a `Protocol`, not a base class, so any object
with the nine methods can be handed to a brain. Three implementations ship:

- `BeliefGrid` (`strategy/belief.py:36`) — the Bayesian filter, the default
- `PointThreat` (`strategy/threat.py:66`) — a known single cell
- `UniformThreat` (`strategy/threat.py:104`) — no information yet

Swap this to replace the inference model without touching the policy that
consumes it. The five tuning constants of the default filter are themselves
constructor parameters (`strategy/belief.py:42`) and config keys
(`belief.smell_trust` and friends, via `from_config`), so tuning needs no
subclass at all — see [RESEARCH.md](RESEARCH.md) for their measured
sensitivity.

## 3. The verbal layer (`trash_talk.provider`)

Banter generation is pluggable and strictly non-authoritative — it never
influences a move (`strategy/decision.py`). Three providers ship: `template`
(pure Python), `ollama` (local), and `glm` (remote). `MODEL_PROVIDERS`
(`strategy/talk.py:30`) is the registry.

`infra/openai_compat.py` is a *generic* OpenAI-compatible client, so any
provider speaking that wire format is reachable by pointing `trash_talk` at it
rather than by writing a new adapter.

## 4. The outbound gate (`Gatekeeper`)

`Gatekeeper` (`shared/gatekeeper_core.py`) takes its limits from an injected
`GateLimits`, and its quota and token bucket are constructor arguments. Two
distinct gates already coexist on that seam — the peer link's
(`infra/mcp_client.py:40`, retries disabled) and the mail reporter's
(`infra/gmail.py:142`, with a daily quota) — which is the seam working as
intended rather than a special case.

Limits come from the agreed `rate_limiter_gatekeeper` block of `game.json`, so
changing them is a negotiation with the opponent, not a code change.

## 5. The application facade (`PoliceAgentSDK`)

`sdk/agent.py:33` is the boundary every front end enters through. The CLI
(`__main__.py`) and the Tk GUI are both just consumers of it; a third front end
(a web UI, a tournament driver) is written against the same methods and needs
no new plumbing. `GameControls` (`peer/controls.py`) is the seam for driving a
running match from outside.

## 6. Config schema versions

`shared/version.py` publishes `SUPPORTED_CONFIG_VERSIONS`, and
`shared/schema.py` maps agreed `game.json` keys onto private ones. A new
config layout is added by extending that map and the supported tuple, which is
why the loader does not have to care whether a peer flattened its TOML.

## Known non-seam

The tunnel is **not** currently pluggable: `sdk/agent_connection.py:75` calls
`infra/tunnel.py`'s ngrok implementation directly, and league validation
(`sdk/league.py:13`) hard-requires `--tunnel` plus a reserved ngrok domain. An
externally managed tunnel therefore cannot be used with `--league`. This is a
real gap, recorded in [TODO.md](TODO.md) rather than papered over here.
