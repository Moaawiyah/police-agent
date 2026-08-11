"""The agreed-terms key set is an interoperability contract. Pin it.

Both peers compare the whole terms dict for equality before playing, so a key we
add or drop unilaterally fails every handshake against an opponent that followed
the course reference -- even when every shared value agrees. That failure mode is
invisible in our own tests, because a peer always agrees with itself.

The literal below is transcribed from the reference's `terms_from_config`. If a
change here is deliberate, it has to be agreed with the other repository first
and this list updated to match; if it is accidental, this test catches it before
a match does.
"""

from police_agent.peer.terms import REQUIRED_TERMS, terms_from_config, validate_agreement
from tests.conftest import config_with

REFERENCE_TERM_KEYS = {
    "board_size",
    "smell_grid_size",
    "decay_per_step",
    "emit_intensity",
    "min_center_intensity",
    "max_steps",
    "barriers_max",
    "setting",
    "hint_max_words",
    "axis_origin_corner",
    "axis_start_index",
    "thief_start",
    "cop_start",
    "num_games",
}


def test_we_sign_exactly_the_reference_key_set(config):
    assert set(terms_from_config(config)) == REFERENCE_TERM_KEYS


def test_the_survival_threshold_is_not_a_signed_term():
    """The reference folds survival into max_steps and never signs it.

    Signing it anyway is what previously broke the handshake, so this is called
    out on its own rather than left implicit in the key-set comparison.
    """
    assert "survival_threshold" not in terms_from_config(config_with())


def test_the_shipped_config_produces_the_values_the_opponent_expects(config):
    """The exact dict the thief's `terms_from_config` builds from the same file."""
    assert terms_from_config(config) == {
        "board_size": 7,
        "smell_grid_size": 5,
        "decay_per_step": 0.10,
        "emit_intensity": 0.9,
        "min_center_intensity": 0.5,
        "max_steps": 35,
        "barriers_max": 14,
        "setting": "New York",
        "hint_max_words": 15,
        "axis_origin_corner": "top-left",
        "axis_start_index": 0,
        "thief_start": [3, 3],
        "cop_start": [0, 0],
        "num_games": 2,
    }


def test_every_required_term_is_one_we_actually_sign(config):
    assert set(REQUIRED_TERMS) <= REFERENCE_TERM_KEYS


def test_the_scent_floor_defaults_rather_than_failing_validation(config):
    """The shipped game.json declares no minimum, and both peers default to 0.5.

    Requiring it without a default would refuse to start on the very file the
    two groups agreed on.
    """
    assert validate_agreement(config)["min_center_intensity"] == 0.5


def test_an_explicitly_declared_scent_floor_wins_over_the_default():
    assert (
        terms_from_config(config_with(smell__min_center_intensity=0.7))["min_center_intensity"]
        == 0.7
    )


def test_a_missing_scent_constant_is_still_refused():
    """Only the floor has a default; the rest must be declared and agreed."""
    import pytest

    from police_agent.exceptions import ConfigError

    with pytest.raises(ConfigError, match="emit_intensity"):
        validate_agreement(config_with(smell__emit_intensity=None))
