"""The agreed terms: the subset of config both peers must hold identically.

Not everything in `game.json` is a term. A peer's port, its strategy selector
and its timeouts are its own business and differ legitimately between the two
sides. What is listed here is what the two agents would *disagree about the game
itself* if it differed -- board size, start cells, the move ceiling, the barrier
quota, the scent constants. Those are signed and compared before play starts.

Keeping the list explicit rather than "hash the whole file" is what allows the
two repositories to evolve independently: a peer may add a private setting to
its own config without breaking the handshake with an opponent that has not.
"""

from typing import Any

from police_agent.exceptions import ConfigError

# Terms with no code default. Playing on a `None` board size would fail deep in
# the first turn with an unrelated-looking error, so absence is caught up front,
# before a port is opened or an opponent is contacted.
REQUIRED_TERMS = (
    "board_size",
    "max_steps",
    "survival_threshold",
    "barriers_max",
    "thief_start",
    "cop_start",
)


def terms_from_config(config: Any) -> dict:
    """The exact object this peer signs and compares against the opponent's.

    Start cells are normalised to lists because the value crosses the wire as
    JSON: a peer that held them as tuples would sign `(0, 0)` and receive
    `[0, 0]`, and the comparison would fail between two peers that actually
    agree.
    """
    return {
        "board_size": config.get("board.size"),
        "max_steps": config.get("rules.max_steps"),
        "survival_threshold": config.get("rules.survival_threshold"),
        "barriers_max": config.get("rules.barriers_max"),
        "thief_start": _as_list(config.get("positions.thief_start")),
        "cop_start": _as_list(config.get("positions.cop_start")),
        "smell_grid_size": config.get("smell.grid_size"),
        "decay_per_step": config.get("smell.decay_per_step"),
        "emit_intensity": config.get("smell.emit_intensity"),
        "setting": config.get("play.setting"),
        "hint_max_words": config.get("play.hint_max_words", 15),
        "axis_origin_corner": config.get("board.axis_origin_corner", "top-left"),
        "axis_start_index": config.get("board.axis_start_index", 0),
    }


def validate_agreement(config: Any) -> dict:
    """Return the terms, or raise ConfigError naming every one that is missing.

    All of them are reported at once: fixing a config one error per run is a
    poor trade when the file is right in front of the person running it.
    """
    terms = terms_from_config(config)
    missing = [name for name in REQUIRED_TERMS if terms.get(name) is None]
    if missing:
        raise ConfigError(
            "Missing required agreed game term(s): "
            + ", ".join(missing)
            + ". These are SHARED terms and must be declared in config/police/game.json "
            "(board_and_agents / movement_and_barriers), byte-identical with the thief's copy."
        )
    return terms


def _as_list(cell: Any) -> Any:
    return list(cell) if isinstance(cell, (list, tuple)) else cell
