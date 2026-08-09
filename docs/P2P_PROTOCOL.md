# Peer-to-peer protocol and transport

## Architecture

Each agent is a separate process. The Police process hosts its own FastMCP
server and acts as a client of the opponent's `/mcp` endpoint. There is no
central server, shared memory, or referee. The turn message is the token: after
receiving a valid opponent turn, the Police folds it into local state, decides,
and sends its own turn.

## Session lifecycle

1. Load the byte-identical shared game terms and the Police-only TOML config.
2. Start the local MCP server and reserve the configured port.
3. Optionally start an ngrok tunnel before dialing the opponent.
4. Open one persistent MCP session and exchange signed terms plus identity.
5. Receive and validate turns, then decide and send turns until a terminal
   result is reached.
6. Exchange audit payloads and close the transport/tunnel.

The server-side handlers validate the outer payload, enqueue it in a mailbox,
and return immediately. They do not run strategy or block on the game loop.
This keeps a slow Police decision from blocking the opponent's HTTP request.

## Wire objects and tools

`TurnMessage` carries the public step, sender, hint, scent grid, timestamp, and
opaque commit, plus optional barrier/capture fields. It deliberately omits the
true position, move, and nonce. `AuditPayload` reveals sealed records only at
the end. `ControlMessage` is advisory session control and is not part of the
scored game record.

The server exposes `negotiate`, `receive_turn`, `submit_audit`, and
`receive_control`. Missing required fields are rejected; unknown fields are
ignored so a compatible peer may send a superset of the Police schema.

## Agreement and timing

The handshake compares the exact agreed-terms dictionary. Board geometry,
starts, step ceiling, barriers, scent terms, hint limit, and series count must
match; ports, strategy choices, and private email settings do not belong in
that comparison. A mismatch prevents play before a bad game begins.

Outbound calls use configured connect/response deadlines, a persistent session,
bounded retry, and one reconnect boundary for a transport drop. Repeated
terminal or post-survival messages are drained and audited without being
mistaken for an additional Police turn.

## Reference-v3 compatibility

`peer/reference_v3.py` isolates the reference dialect: compact sorted JSON,
reference commit bytes, strict turn validation, optional-field translation,
and audit handling. The native protocol remains available to local fakes and
older Police peers. Compatibility-sensitive details include tool names,
field names, scent timing, and terminal-message handling.

## Public networking

Local practice uses a peer URL such as
`http://127.0.0.1:8802/mcp`. Public play uses `--tunnel`; the tunnel publishes
the already-bound MCP port and returns the public URL with `/mcp` appended. A
league run additionally requires `--league`, an HTTPS public opponent URL, and
a configured reserved domain. See
[INTEROPERABILITY_AND_OPERATIONS.md](INTEROPERABILITY_AND_OPERATIONS.md).

## Implementation and tests

- Server/client: [`infra/mcp_server.py`](../src/police_agent/infra/mcp_server.py)
  and [`infra/mcp_client.py`](../src/police_agent/infra/mcp_client.py).
- Contract/runtime: [`peer/protocol.py`](../src/police_agent/peer/protocol.py),
  [`peer/terms.py`](../src/police_agent/peer/terms.py),
  [`peer/handshake.py`](../src/police_agent/peer/handshake.py), and
  [`peer/runtime.py`](../src/police_agent/peer/runtime.py).
- Tests: [`tests/peer/`](../tests/peer/) and socket/infrastructure tests under
  [`tests/infra/`](../tests/infra/).

## Open boundaries

Opening a socket is not proof of a match. A valid interoperability result
requires both process exits, mutually consistent results, completed audit
records, and closed listeners. This repository proves the Police role only;
it does not provide a Police-as-thief engine or role-swapping proof.
