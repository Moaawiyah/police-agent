"""The seam between the agreed `game.json` and the keys this code reads.

The shared file's shape is fixed by the specification (Appendix Vav) and must be
held byte-identical by both peers, so it cannot be reorganised to suit our
package layout. Translating it once, here, means the external schema is named in
exactly one place: if the course changes a key, this table changes and nothing
else does.

The translation is deliberately a data table rather than code. A missing source
key is simply not emitted, so a partial `game.json` yields a partial config and
the missing term is reported later by the agreement check -- with the term's
name -- instead of surfacing as a `None` crash mid-game.
"""

from typing import Any

# (path in the agreed game.json, dotted key the code asks for)
_TRANSLATION: tuple[tuple[str, str], ...] = (
    ("board_and_agents.grid_size", "board.size"),
    ("board_and_agents.cop_start", "positions.cop_start"),
    ("board_and_agents.thief_start", "positions.thief_start"),
    ("board_and_agents.axis_origin_corner", "board.axis_origin_corner"),
    ("board_and_agents.axis_start_index", "board.axis_start_index"),
    ("world.map_area", "play.setting"),
    ("world.hint_max_words", "play.hint_max_words"),
    ("movement_and_barriers.max_barriers", "rules.barriers_max"),
    ("movement_and_barriers.max_moves", "rules.max_steps"),
    ("movement_and_barriers.survival_threshold", "rules.survival_threshold"),
    ("pheromones.pheromone_center_intensity", "smell.emit_intensity"),
    ("pheromones.pheromone_decay", "smell.decay_per_step"),
    ("pheromones.pheromone_grid_size", "smell.grid_size"),
    # Reference-v3 names the selected emission table and the disclosure delay
    # explicitly. They are not signed terms, but they still have to reach the
    # scent layer so both peers run the same physics.
    ("pheromones.pheromone_kernel", "smell.kernel"),
    ("pheromones.pheromone_sigma_sq", "smell.sigma_sq"),
    ("pheromones.pheromone_transmit_lag", "smell.transmit_lag"),
    # Absent from the shipped game.json; both peers fall back to the same agreed
    # default (see peer/terms.py). Mapped so an explicit value would still win.
    ("pheromones.pheromone_min_center_intensity", "smell.min_center_intensity"),
    ("network_and_league.response_timeout_sec", "network.response_timeout_seconds"),
    ("network_and_league.watchdog_timeout_sec", "network.watchdog_timeout_seconds"),
    ("network_and_league.num_games", "game.num_games"),
    ("network_and_league.num_sub_games", "game.num_games"),
    ("network_and_league.token_budget_per_series", "game.token_budget_per_series"),
    # Appendix Vav table 19, the Gatekeeper's limits. Every one is status
    # "minimum": absent from the agreed file, `shared/gatekeeper.py` supplies the
    # example value rather than leaving the door unguarded.
    ("rate_limiter_gatekeeper.requests_per_minute", "gatekeeper.requests_per_minute"),
    ("rate_limiter_gatekeeper.concurrent_requests", "gatekeeper.concurrent_requests"),
    ("rate_limiter_gatekeeper.retry_backoff_sec", "gatekeeper.retry_backoff_seconds"),
    ("rate_limiter_gatekeeper.max_retries", "gatekeeper.max_retries"),
    ("rate_limiter_gatekeeper.queue_depth", "gatekeeper.queue_depth"),
)


def dig(data: dict, dotted: str, default: Any = None) -> Any:
    """Read a nested value by dotted path, or `default` if any step is absent."""
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def put(target: dict, dotted: str, value: Any) -> None:
    """Write a nested value by dotted path, creating the sections it needs."""
    parts = dotted.split(".")
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def translate_shared(shared: dict) -> dict:
    """Map the agreed `game.json` onto the internal dotted namespace.

    The scoring block is copied across whole: its keys are already the names the
    scoring table uses, so renaming them would only add a second vocabulary.
    """
    out: dict = {}
    sentinel = object()
    for source, target in _TRANSLATION:
        value = dig(shared, source, sentinel)
        if value is not sentinel:
            put(out, target, value)
    if "scoring" in shared:
        out["scoring"] = dict(shared["scoring"])
    return out


def deep_merge(base: dict, overlay: dict) -> None:
    """Merge `overlay` into `base` in place; a leaf in `overlay` wins."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
