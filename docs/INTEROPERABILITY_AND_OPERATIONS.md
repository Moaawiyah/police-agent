# Interoperability and operations

## Install and prepare

From the Police checkout:

```text
uv sync
Copy-Item config/police/game.toml.example config/police/game.toml
```

Set the private port and opponent URL. Keep `config/police/game.json`
byte-identical to the opponent's agreed file. Do not fill credentials into a
tracked template or commit `game.toml`, `credentials.json`, or `token.json`.

## Local two-process run

Start the thief from its own repository and the Police from this repository,
using different ports and each peer's own configuration. A local endpoint has
the shape `http://127.0.0.1:<port>/mcp`. Use `--summary` for a standalone
record, `--series` for all agreed sub-games, and `--report` when the report
path should be exercised.

## Public/league run

For peers on different machines:

```text
ngrok config add-authtoken <your token>
uv run police-agent --tunnel
uv run police-agent --league --tunnel
```

The token belongs to ngrok's own configuration and is never read by this
project. A league run requires an HTTPS public opponent URL and a reserved
domain. A free ngrok account may allow only one tunnel at a time; stop only the
tunnel owned by the run when cleanup is needed.

## Interoperability contract

An external thief must honor the agreed terms, public turn fields, commit/reveal
shape, one-turn scent timing, capture claim echo, terminal-message behavior,
and audit record coverage. Reference-v3 compatibility is isolated in
[`peer/reference_v3.py`](../src/police_agent/peer/reference_v3.py) so exact
commit bytes and strict validation are not accidentally changed by native
protocol work.

The strongest acceptance evidence is a completed two-process match with
mutually agreed results, verified replays/audits, and closed ports. A started
process, open socket, or distinct log hash by itself is not sufficient.

## Validation checklist

```text
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run police-agent --help
```

For a public run, additionally confirm the tunnel URL is HTTPS, the opponent
dials `/mcp`, both processes exit, result files agree, audits pass, and the
tunnel/ports close. Keep generated logs and match artifacts outside the
committed source diff unless they are explicitly required as evidence.

## Current evidence boundary

Automated tests cover the protocol, reference dialect, reporting, GUI seams,
and failure paths. Police-as-cop reference interoperability is a narrower
claim than full role-swapping support; this repository contains no thief-role
engine. Live Gmail delivery, authenticated reserved-domain tunneling, and
submission screenshots require their own deliberate runs.
