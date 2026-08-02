"""The scent field as it crosses the wire: what goes out, and what comes back.

Everything here is a boundary with another team's implementation, so the tests
lean on the two properties that matter at a boundary: the format round-trips,
and bad input is survived rather than raised on.
"""

import pytest

from tests.conftest import scent_field


class TestEmit:
    def test_a_freshly_laid_trail_goes_out_at_the_agreed_intensity(self):
        """Decay is applied before the deposit, so the new cell is not born stale."""
        grid = scent_field().emit((3, 3))

        assert grid["3,3"] == 0.9
        assert round(grid["3,4"], 2) == 0.62

    def test_the_previous_position_is_left_behind_as_a_weaker_trail(self):
        """Ch. 4.4 reads exactly this: last turn's cell at (1 - rho) * 0.9 = 0.81."""
        scent = scent_field()
        scent.emit((3, 3))

        grid = scent.emit((3, 4))

        assert grid["3,4"] == 0.9  # where the agent is now
        assert grid["3,3"] == 0.81  # where it was, one turn staler

    def test_the_grid_is_a_field_and_not_a_single_cell(self):
        """A point mass would hand the opponent an exact position (Appendix He, 27)."""
        grid = scent_field().emit((3, 3))

        assert len(grid) > 1
        assert all("," in key for key in grid)


class TestAbsorb:
    def test_a_received_grid_merges_with_the_stronger_value_winning(self):
        scent = scent_field()
        scent.absorb({"2,2": 0.4})
        scent.absorb({"2,2": 0.7, "5,5": 0.2})

        assert scent.intensity_at((2, 2)) == 0.7
        assert scent.intensity_at((5, 5)) == 0.2

    @pytest.mark.parametrize(
        "grid",
        [
            {"not-a-cell": 0.9},
            {"9,9": 0.9},  # off-board
            {"1,1": "loud"},  # not a number
            {"1": 0.9},  # missing a coordinate
            None,
        ],
    )
    def test_junk_from_another_teams_implementation_is_skipped_not_fatal(self, grid):
        scent = scent_field()
        scent.absorb(grid)

        assert scent.snapshot() == {}  # nothing absorbed, and nothing raised

    def test_a_usable_cell_survives_alongside_junk(self):
        scent = scent_field()
        scent.absorb({"bad": 1.0, "2,4": 0.6})

        assert scent.intensity_at((2, 4)) == 0.6


class TestSnapshot:
    def test_the_wire_form_round_trips_through_a_second_field(self):
        source = scent_field()
        source.deposit((3, 3))

        mirror = scent_field()
        mirror.absorb(source.snapshot())

        assert mirror.snapshot() == source.snapshot()

    def test_an_untouched_field_smells_of_nothing(self):
        scent = scent_field()

        assert scent.snapshot() == {}
        assert scent.intensity_at((3, 3)) == 0.0

    def test_the_same_readings_produce_the_same_grid_whatever_order_they_arrive(self):
        """Both peers must derive identical fields, so this cannot depend on order."""
        forward, backward = scent_field(), scent_field()
        forward.absorb({"1,1": 0.5, "2,2": 0.7})
        backward.absorb({"2,2": 0.7, "1,1": 0.5})

        assert forward.snapshot() == backward.snapshot()
