# SDK, CLI, and configuration

## SDK boundary

`PoliceAgentSDK` is the composition root for front ends. It loads the layered
configuration, resolves endpoints, starts the local server, opens the
transport/tunnel, constructs the runtime, and exposes match/report operations.
Domain rules remain in `domain/` and peer orchestration remains in `peer/`.

Typical programmatic use:

```python
from police_agent.sdk import MatchOptions, PoliceAgentSDK

agent = PoliceAgentSDK(MatchOptions(port=8801, opponent_url="http://127.0.0.1:8802/mcp"))
agent.connect()
summary = agent.play()
agent.save_summary(summary, "result.json")
```

The SDK accepts injectable config, transport, listener, and controls so tests
and front ends do not need to create a real opponent or window.

## CLI modes

The `police-agent` command supports:

- normal one-sub-game headless play;
- `--series` for the whole agreed series;
- `--gui` for live play with the board window;
- `--replay` with optional `--opponent-log`;
- `--export` for GIF/MP4 replay output;
- `--summary`, `--report`, and `--report-dir` for artifacts/email;
- `--tunnel` and `--league` for public/league validation;
- `--host`, `--port`, `--opponent`, and `--config-dir` overrides.

Run `uv run police-agent --help` for the current flag spelling.

## Configuration layers

- `config/police/game.json` contains shared physics, scoring, scent, identity,
  and series terms. It must be byte-identical with the opponent's copy.
- `config/police/game.toml` is private and is created from
  [`game.toml.example`](../config/police/game.toml.example). It contains local
  ports, opponent URL, strategy/model choices, tunnel domain, GUI pacing, and
  email paths.
- The loader overlays the agreed terms on the private settings so a local
  setting cannot silently replace the shared game rules.

Credentials and private `game.toml` must never be committed. The optional
Gmail files are ignored; see [GMAIL_SETUP.md](GMAIL_SETUP.md).

## Implementation and tests

- [`sdk/options.py`](../src/police_agent/sdk/options.py),
  [`sdk/agent.py`](../src/police_agent/sdk/agent.py),
  [`sdk/reporting.py`](../src/police_agent/sdk/reporting.py), and
  [`sdk/league.py`](../src/police_agent/sdk/league.py)
- [`__main__.py`](../src/police_agent/__main__.py) and
  [`cli_args.py`](../src/police_agent/cli_args.py)
- [`shared/config.py`](../src/police_agent/shared/config.py) and
  [`shared/schema.py`](../src/police_agent/shared/schema.py)
- Tests: [`tests/sdk/`](../tests/sdk/) and
  [`tests/shared/test_config.py`](../tests/shared/test_config.py)

## Open boundaries

Tunnel and league options are deliberately opt-in because opening a practice
match to the internet is a meaningful side effect. Front ends may add UI or
automation through the SDK seams without moving game logic into the CLI.
