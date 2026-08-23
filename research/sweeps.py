"""One-at-a-time sensitivity sweeps over the police's tunable constants.

One-at-a-time rather than a full factorial: with nine parameters a grid is
thousands of times more episodes for an interaction effect nobody has evidence
for yet, and OAT answers the question actually being asked -- is this constant's
shipped value defensible, and how sharp is the optimum around it.

Every point re-runs the *same* seed range, so two settings are compared on the
same episodes rather than on independently sampled ones. That is what makes a
small difference readable at a few hundred episodes instead of needing tens of
thousands.

Belief constants are constructor arguments (`strategy/belief.py:42`), so they
are passed in. The strategy constants are module-level, so they are patched at
the module that *binds* them -- `brain.py` imports `TOP_K` by value, so patching
`placement.TOP_K` would not reach it. `STRATEGY_TARGETS` records the real
binding site for each, which is also why it is data rather than a guess.
"""

import statistics
from contextlib import contextmanager
from dataclasses import dataclass

from research.evader import FLEE
from research.harness import play

EPISODES = 500

# name -> (module that binds it, attribute). See the module docstring.
STRATEGY_TARGETS = {
    "TOP_K": ("police_agent.strategy.brain", "TOP_K"),
    "ESCAPE_WEIGHT": ("police_agent.strategy.placement", "ESCAPE_WEIGHT"),
    "WIDE_REACH": ("police_agent.strategy.barrier", "WIDE_REACH"),
    "MIN_GAIN_FRACTION": ("police_agent.strategy.encirclement", "MIN_GAIN_FRACTION"),
    "MIN_GAIN_FLOOR": ("police_agent.strategy.encirclement", "MIN_GAIN_FLOOR"),
}

BELIEF_PARAMS = ("smell_trust", "smell_power", "leak", "stale_decay", "stale_support")


@dataclass(frozen=True)
class Point:
    """One parameter value and the aggregate of the episodes it was scored on."""

    value: float
    episodes: int
    capture_rate: float
    mean_steps: float
    hit_rate: float
    mean_error: float
    mean_true_prob: float

    @property
    def capture_se(self) -> float:
        """Standard error of the capture rate, treating it as a binomial proportion.

        Conservative on purpose. Every point in a sweep replays the *same* seeds,
        so two settings are a paired comparison and the error on their difference
        is smaller than this. Quoting the unpaired figure keeps a claim from
        resting on the pairing being perfect.
        """
        p = self.capture_rate
        return (p * (1.0 - p) / self.episodes) ** 0.5

    @property
    def capture_ci95(self) -> tuple[float, float]:
        """A 95% normal-approximation interval around the capture rate."""
        half = 1.96 * self.capture_se
        return (max(0.0, self.capture_rate - half), min(1.0, self.capture_rate + half))


def aggregate(value: float, episodes: list) -> Point:
    """Reduce a batch of episodes to the five reported statistics."""
    return Point(
        value=value,
        episodes=len(episodes),
        capture_rate=sum(e.captured for e in episodes) / len(episodes),
        mean_steps=statistics.mean(e.steps for e in episodes),
        hit_rate=statistics.mean(e.hit_rate for e in episodes),
        mean_error=statistics.mean(e.mean_error for e in episodes),
        mean_true_prob=statistics.mean(e.mean_true_prob for e in episodes),
    )


@contextmanager
def patched(name: str, value):
    """Temporarily rebind a strategy constant at the module that binds it."""
    import importlib

    module_path, attribute = STRATEGY_TARGETS[name]
    module = importlib.import_module(module_path)
    original = getattr(module, attribute)
    setattr(module, attribute, value)
    try:
        yield
    finally:
        setattr(module, attribute, original)


def sweep_belief(name: str, values, *, episodes: int = EPISODES, policy: str = FLEE) -> list[Point]:
    """Vary one belief constant, holding the other four at their shipped defaults."""
    if name not in BELIEF_PARAMS:
        raise ValueError(f"{name!r} is not a belief parameter; expected one of {BELIEF_PARAMS}")
    return [
        aggregate(v, [play(s, policy=policy, belief={name: v}) for s in range(episodes)])
        for v in values
    ]


def sweep_strategy(
    name: str, values, *, episodes: int = EPISODES, policy: str = FLEE
) -> list[Point]:
    """Vary one strategy constant, holding the rest at their shipped defaults."""
    if name not in STRATEGY_TARGETS:
        raise ValueError(f"{name!r} is not a strategy constant; expected {list(STRATEGY_TARGETS)}")
    results = []
    for value in values:
        with patched(name, value):
            results.append(aggregate(value, [play(s, policy=policy) for s in range(episodes)]))
    return results
