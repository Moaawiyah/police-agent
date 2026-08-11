"""The strategy seam: the police move policy, chosen at start-up.

Which brain runs is configuration, not code. `config/police/game.toml.example`
exposes an optional `[strategy] police_class` selector holding a dotted
``"package.module:ClassName"``; with no selector the shipped `PoliceBrain` runs.
That is what lets a new heuristic be tried, and a submitted game re-run with the
exact brain it was played with, without editing the runtime.

The already-parsed config is passed in rather than loaded here: strategy has no
business reading files, and the loader is a separate concern that this package
must not be coupled to. Any mapping answering `.get()` will do, including
`None`.
"""

import importlib
import random
from typing import Any

from police_agent.strategy.brain import PoliceBrain, PoliceBrainBase
from police_agent.strategy.decision import Decision
from police_agent.strategy.encirclement import WIDE_REACH
from police_agent.strategy.threat import PointThreat, ThreatEstimate, UniformThreat

__all__ = [
    "WIDE_REACH",
    "Decision",
    "PoliceBrain",
    "PoliceBrainBase",
    "PointThreat",
    "ThreatEstimate",
    "UniformThreat",
    "load_brain_cls",
    "resolve_brain",
    "resolve_brain_cls",
]

_SELECTOR_KEY = "strategy.police_class"


def load_brain_cls(dotted: str) -> type[PoliceBrainBase]:
    """Import a brain class from a ``"package.module:ClassName"`` selector.

    Every failure is raised rather than silently falling back to the default: a
    game played with the wrong brain because of a typo in the config would be
    unreproducible and, worse, would look like it ran correctly.
    """
    module_path, separator, class_name = dotted.partition(":")
    if not separator or not module_path or not class_name:
        raise ValueError(f"strategy selector must be 'package.module:ClassName', got {dotted!r}")
    module = importlib.import_module(module_path)
    try:
        brain_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(f"{class_name!r} not found in module {module_path!r}") from exc
    if not (isinstance(brain_cls, type) and issubclass(brain_cls, PoliceBrainBase)):
        raise TypeError(f"{dotted!r} does not name a PoliceBrainBase subclass")
    return brain_cls


def resolve_brain_cls(config: Any = None) -> type[PoliceBrainBase]:
    """The configured brain class, or the shipped `PoliceBrain` when unset."""
    selector = _selector(config)
    return load_brain_cls(str(selector)) if selector else PoliceBrain


def resolve_brain(config: Any = None, rng: random.Random | None = None) -> PoliceBrainBase:
    """Instantiate the configured brain. This is the only constructor the runtime calls."""
    return resolve_brain_cls(config)(rng=rng)


def _selector(config: Any) -> Any:
    """Read the selector from either a flattened or a nested config mapping.

    A config manager may flatten TOML into dotted keys, while raw `tomllib`
    output keeps `[strategy]` as a nested table. Reading both means this package
    does not have to care which one the loader ends up being.
    """
    if config is None:
        return None
    flat = config.get(_SELECTOR_KEY)
    if flat:
        return flat
    section = config.get("strategy")
    return section.get("police_class") if isinstance(section, dict) else None
