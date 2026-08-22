"""Regenerate every figure and the raw result table: `uv run python -m research`.

Takes an optional episode count (`python -m research 100`) so the whole study
can be re-run cheaply while iterating, then once at full size for the report.
"""

import json
import sys
from pathlib import Path

from research import evader
from research.grid import BELIEF, STRATEGY
from research.plots import capture_curve, tracking_curve
from research.sweeps import EPISODES, sweep_belief, sweep_strategy

DATA = Path(__file__).resolve().parents[1] / "docs" / "research-data.json"


def _row(point) -> dict:
    """One point, flattened for the JSON record."""
    low, high = point.capture_ci95
    return {
        "value": point.value,
        "capture_rate": round(point.capture_rate, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "mean_steps": round(point.mean_steps, 2),
        "hit_rate": round(point.hit_rate, 4),
        "mean_error": round(point.mean_error, 3),
        "mean_true_prob": round(point.mean_true_prob, 4),
    }


def run(episodes: int = EPISODES) -> dict:
    """Run both studies, write the figures, and return the collected numbers."""
    collected = {"episodes": episodes, "policy": evader.FLEE, "belief": {}, "strategy": {}}
    for name, (values, shipped) in BELIEF.items():
        points = sweep_belief(name, values, episodes=episodes)
        capture_curve(points, name, shipped, f"fig-belief-{name.replace('_', '-')}.png")
        tracking_curve(points, name, shipped, f"fig-track-{name.replace('_', '-')}.png")
        collected["belief"][name] = {"shipped": shipped, "points": [_row(p) for p in points]}
        print(f"  belief/{name}: {len(points)} points")
    for name, (values, shipped) in STRATEGY.items():
        points = sweep_strategy(name, values, episodes=episodes)
        capture_curve(points, name, shipped, f"fig-strategy-{name.lower().replace('_', '-')}.png")
        collected["strategy"][name] = {"shipped": shipped, "points": [_row(p) for p in points]}
        print(f"  strategy/{name}: {len(points)} points")
    return collected


def main(argv: list[str] | None = None) -> int:
    """Run the study at the requested size and write `docs/research-data.json`."""
    argv = sys.argv[1:] if argv is None else argv
    episodes = int(argv[0]) if argv else EPISODES
    print(f"running the sensitivity study at {episodes} episodes/point")
    collected = run(episodes)
    DATA.write_text(json.dumps(collected, indent=2) + "\n")
    print(f"wrote {DATA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
