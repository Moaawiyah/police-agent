# Core gameplay and deterministic rules

## Purpose

The Police agent plays on a shared finite grid without ever storing the
thief's true live position. The domain layer owns geometry, legal actions,
the Police player's state, terminal rules, and scoring. It is independent of
FastMCP, the GUI, and language-model code.

## Board and actions

- A position is a `(row, column)` cell inside the configured square board.
- Movement is orthogonal: north, south, east, west, or `HOLD:-`.
- Diagonal movement, out-of-bounds movement, and movement through a declared
  barrier are illegal.
- A validated `Action` describes either a step/hold or a barrier placement.
- `Board.legal_moves()` and `Board.barrier_targets()` are the single geometry
  helpers used by state and strategy code.

The Police state records only its own position, visited cells, declared
barriers, quota usage, and sealed local log. The thief's position is a belief
in the strategy layer and appears only after an end-of-game reveal.

## Barriers

A Police barrier consumes the turn instead of moving. Its target is the Police
cell or one of the four adjacent cells, subject to bounds, existing barriers,
and the configured quota. The state rejects a placement that would leave the
Police with no legal move. The strategy layer decides when a legal barrier is
worth spending; the domain layer only validates and applies it.

The detailed policy is in
[mechanisms/PRD-barrier-strategy.md](mechanisms/PRD-barrier-strategy.md).

## Outcomes and scoring

The runtime stops on capture, survival, timeout, an audit failure, or another
technical terminal condition. The Police does not invent the thief-only
barrier/confinement facts during live play; those claims are checked against
revealed records during the semantic audit.

`score_subgame()` converts one outcome into the points for each group's role.
`aggregate()` sums a series, counts sub-game wins and ties, applies the agreed
tie score, and reports the series winner. Values come from the shared scoring
terms rather than being embedded in the strategy.

## Determinism and privacy

The rules engine is deterministic and contains no network calls, GUI state, or
LLM decision. Optional language output is generated after the move has been
selected and cannot change it. A live Police process never receives or stores
the opponent's true cell; a revealed opponent log is an audit/replay input,
not live decision information.

## Implementation and tests

- Implementation: [`domain/board.py`](../src/police_agent/domain/board.py),
  [`domain/actions.py`](../src/police_agent/domain/actions.py),
  [`domain/own_state.py`](../src/police_agent/domain/own_state.py),
  [`domain/rules.py`](../src/police_agent/domain/rules.py), and
  [`domain/scoring.py`](../src/police_agent/domain/scoring.py).
- Tests: [`tests/domain/`](../tests/domain/), especially board, actions, rules,
  own-state, and scoring tests.

## Open boundaries

The Police repository intentionally does not implement the thief agent or a
shared live board. Cross-repository capture timing and any claim that depends
on the thief's hidden position must remain in the signed audit contract.
