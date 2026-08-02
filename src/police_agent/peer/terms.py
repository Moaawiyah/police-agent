"""The agreed terms: the subset of config both peers must hold identically.

Not everything in `game.json` is a term. A peer's port, its strategy selector
and its timeouts are its own business and differ legitimately between the two
sides. What is listed here is what the two agents would *disagree about the game
itself* if it differed -- board size, start cells, the move ceiling, the barrier
quota, the scent constants.

**This list is an interoperability contract, not a design choice.** Both peers
compare the whole dict for equality before playing, so a key present on one side
and absent on the other fails the handshake even when every shared value agrees.
The key set below is therefore copied exactly from the course reference
implementation, which is what the opposing agent implements: adding a term we
consider important, or dropping one we do not use, breaks every match against
anyone who followed the reference. `tests/peer/test_terms_contract.py` pins the
key set so it cannot drift back.

The most visible consequence is that `survival_threshold` is *not* here. The
reference folds survival into `max_steps` and never signs it separately. It is
still read from the shared, byte-identical `game.json`, so both peers agree on
it in practice -- but that agreement is unsigned, and a peer that edited only
its own copy would not be caught by the handshake.
"""

from typing import Any

from police_agent.exceptions import ConfigError

# Terms with no code default: absence means the shared game.json is incomplete,
# and playing on a `None` board size would fail deep in the first turn with an
# unrelated-looking error. Caught before a port is opened or an opponent is
# contacted. Mirrors the reference's REQUIRED_TERMS.
REQUIRED_TERMS = (
    "board_size",
    "smell_grid_size",
    "decay_per_step",
    "emit_intensity",
    "min_center_intensity",
    "max_steps",
    "barriers_max",
    "thief_start",
    "cop_start",
)

# The agreed scent floor when the shared file does not declare one. The value
# matches the reference and the opposing thief; changing it unilaterally would
# fail every handshake, which is exactly what a signed term is for.
DEFAULT_MIN_CENTER_INTENSITY = 0.5


def terms_from_config(config: Any) -> dict:
    """The exact object this peer signs and compares against the opponent's.

    Key-for-key identical to the reference. Start cells are normalised to lists
    because the value crosses the wire as JSON: a peer that held them as tuples
    would sign `(0, 0)` and receive `[0, 0]`, and the comparison would fail
    between two peers that actually agree.
    """
    return {
        "board_size": config.get("board.size"),
        "smell_grid_size": config.get("smell.grid_size"),
        "decay_per_step": config.get("smell.decay_per_step"),
        "emit_intensity": config.get("smell.emit_intensity"),
        "min_center_intensity": config.get(
            "smell.min_center_intensity", DEFAULT_MIN_CENTER_INTENSITY
        ),
        "max_steps": config.get("rules.max_steps"),
        "barriers_max": config.get("rules.barriers_max"),
        "setting": config.get("play.setting"),
        "hint_max_words": config.get("play.hint_max_words", 15),
        "axis_origin_corner": config.get("board.axis_origin_corner", "top-left"),
        "axis_start_index": config.get("board.axis_start_index", 0),
        "thief_start": _as_list(config.get("positions.thief_start")),
        "cop_start": _as_list(config.get("positions.cop_start")),
        "num_games": config.get("game.num_games", 1),
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
            "(board_and_agents / movement_and_barriers / pheromones), byte-identical "
            "with the thief's copy."
        )
    return terms


def _as_list(cell: Any) -> Any:
    return list(cell) if isinstance(cell, list | tuple) else cell
