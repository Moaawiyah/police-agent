# Series execution, artifacts, and reporting

## One game and a whole series

Normal headless play runs one sub-game. `--series` runs `game.num_games`
sub-games in sequence; `--gui` uses the same whole-series behavior while
showing the live board. Each sub-game has its own record and audit, while the
final result aggregates sibling records from the report directory.

`domain/scoring.py` converts each outcome to role-aware points and applies the
agreed tie rule. A technical loss is not treated as a capture or survival.

## Step-zero and artifact set

Before the first move, the runtime seals the step-zero hardware/code
declaration. Reporting then writes game-derived files under
`logs/<group_id>/`:

```text
declaration_<game_id>.json
config_<game_id>_gNN.json
log_<game_id>_gNN.json
record_<game_id>_gNN.json
result_<game_id>.json
```

The config and log files describe one sub-game. The declaration spans the
series. The result covers the completed series and carries the links/digests
needed by the receiving grader. Filenames are derived from the game identity
so records from unrelated matches are not mixed.

## Gmail delivery

`--report` writes and sends a one-sub-game report. Series play writes all
sub-game artifacts and invokes the independent report once at the end. Gmail
is disabled by default; `mode = "draft"` creates a local `.eml`, while
`mode = "send"` uses the optional Gmail dependency and the send-only OAuth
scope. Follow [GMAIL_SETUP.md](GMAIL_SETUP.md) for the human authorization
steps. Credentials and tokens remain outside Git.

Every real send passes the persisted daily quota and the provider gate. A
bounded/retried provider failure is reported as unsent rather than changing
the game result.

## Implementation and tests

- Artifact construction: [`report/`](../src/police_agent/report/)
- SDK/CLI reporting: [`sdk/reporting.py`](../src/police_agent/sdk/reporting.py),
  [`cli_actions.py`](../src/police_agent/cli_actions.py), and
  [`peer/series.py`](../src/police_agent/peer/series.py)
- Email: [`infra/gmail.py`](../src/police_agent/infra/gmail.py) and
  [`infra/gmail_client.py`](../src/police_agent/infra/gmail_client.py)
- Tests: [`tests/report/`](../tests/report/),
  [`tests/infra/test_gmail.py`](../tests/infra/test_gmail.py), and
  [`tests/sdk/test_agent_series.py`](../tests/sdk/test_agent_series.py)

## Open boundaries

The local draft path and stand-in client are testable without Google. A real
OAuth-authorized send must still be rehearsed deliberately before it is called
live-verified. The final result also depends on all required peer reports being
present; writing local JSON alone is not proof of successful delivery.
