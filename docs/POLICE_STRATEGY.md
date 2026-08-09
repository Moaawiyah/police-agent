# Police strategy, scent, and belief

## Decision pipeline

One Police turn follows this order:

1. Receive the opponent's public turn and scent grid.
2. Predict possible thief locations with `BeliefGrid.diffuse()`.
3. Update the belief with the new scent using `observe_smell()`.
4. Read an optional hint claim and apply it only according to its earned
   reliability.
5. Estimate the most likely cell through the `ThreatEstimate` interface.
6. Select a barrier when it removes meaningful escape space; otherwise move
   toward the believed target using legal geometry.
7. Apply and seal the action in the domain state.

The live policy never receives the thief's true position. The belief matrix is
the only location estimate available to strategy code.

## Scent and Bayesian belief

`ScentField` emits the configured radial field and applies the agreed decay.
`BeliefGrid` starts from a valid prior, predicts over legal orthogonal motion,
weights cells by the received scent, normalizes, and can exclude impossible
cells. The belief is kept separate from the physical Police state so a display
or replay cannot accidentally become an authority.

The detailed algorithm contract is in
[mechanisms/PRD-belief-scent.md](mechanisms/PRD-belief-scent.md).

## Chase and barriers

The shipped brain is deterministic. It prefers actions that reduce the
Manhattan distance to the believed cell, with the configured tie-breaking
behavior. Close-range barriers are considered only when they remove a legal
escape within the barrier reach and do not confine the Police. The wide-range
path evaluates reachable-pocket reduction through `encirclement.py` and spends
quota only when the gain passes its gate.

The strategy is a replaceable seam: `[strategy] police_class` can select a
custom `PoliceBrainBase` implementation without changing domain rules or the
peer runtime.

## Hint reliability

`BluffAnalyst` compares a claimed compass direction with the freshest scent
evidence, maintains a smoothed reliability estimate, and avoids counting the
same turn's scent twice. A claim may reweight belief only when the evidence
policy permits it. The summary records `opponent_reliability` and
`hint_readings`.

## Configuration and source

Private tuning lives in `game.toml`, including `belief.smell_trust`,
`belief.smell_power`, and `bluff.gain`. Shared scent constants remain in the
agreed `game.json`; changing them is a protocol/configuration change, not a
local strategy tweak.

Implementation: [`strategy/brain.py`](../src/police_agent/strategy/brain.py),
[`strategy/barrier.py`](../src/police_agent/strategy/barrier.py),
[`strategy/encirclement.py`](../src/police_agent/strategy/encirclement.py),
[`strategy/belief.py`](../src/police_agent/strategy/belief.py),
[`strategy/bluff.py`](../src/police_agent/strategy/bluff.py), and
[`peer/turn_handler.py`](../src/police_agent/peer/turn_handler.py).

Tests are grouped under [`tests/strategy/`](../tests/strategy/) and
[`tests/domain/test_scent.py`](../tests/domain/test_scent.py).

## Open tuning items

The model has private tuning parameters whose best values depend on live
opponents. A unit-test pass proves the update laws and legal decisions, not
competitive performance. Reliability currently starts per sub-game, and the
landmark names in free-text hints do not map to board regions.
