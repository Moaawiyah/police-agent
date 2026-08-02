"""The interim threat estimate: read the strongest scent, survive bad input."""

import pytest

from police_agent.strategy.scent_threat import ScentThreat
from police_agent.strategy.threat import ThreatEstimate


def test_it_satisfies_the_threat_protocol_the_brain_consumes():
    assert isinstance(ScentThreat(7), ThreatEstimate)


def test_the_centre_is_the_answer_before_anything_has_arrived():
    assert ScentThreat(7).most_likely() == (3, 3)
    assert ScentThreat(6).most_likely() == (2, 2)


def test_the_strongest_cell_wins():
    threat = ScentThreat(7)
    threat.absorb({"0,0": 0.2, "6,6": 0.9, "3,3": 0.5})

    assert threat.most_likely() == (6, 6)


def test_a_later_grid_replaces_the_earlier_one():
    """No prior is kept -- this is the placeholder, not the belief map."""
    threat = ScentThreat(7)
    threat.absorb({"0,0": 0.9})
    threat.absorb({"5,5": 0.1})

    assert threat.most_likely() == (5, 5)


def test_an_empty_grid_leaves_the_last_estimate_standing():
    threat = ScentThreat(7)
    threat.absorb({"1,1": 0.7})
    threat.absorb({})

    assert threat.most_likely() == (1, 1)


def test_ties_resolve_the_same_way_every_time():
    """The strategy above this is deterministic and needs a deterministic input."""
    grids = [{"1,1": 0.5, "2,2": 0.5}, {"2,2": 0.5, "1,1": 0.5}]

    answers = set()
    for grid in grids:
        threat = ScentThreat(7)
        threat.absorb(grid)
        answers.add(threat.most_likely())

    assert answers == {(1, 1)}


@pytest.mark.parametrize(
    "grid",
    [
        {"not-a-cell": 0.9},
        {"9,9": 0.9},  # off-board
        {"1,1": "loud"},  # not a number
        {"1": 0.9},  # missing a coordinate
    ],
)
def test_junk_from_another_teams_implementation_is_skipped_not_fatal(grid):
    threat = ScentThreat(7)
    threat.absorb(grid)

    assert threat.most_likely() == (3, 3)  # fell back to the centre, did not raise


def test_a_usable_cell_survives_alongside_junk():
    threat = ScentThreat(7)
    threat.absorb({"bad": 1.0, "2,4": 0.6})

    assert threat.most_likely() == (2, 4)


def test_a_board_must_have_cells():
    with pytest.raises(ValueError, match="must be positive"):
        ScentThreat(0)
