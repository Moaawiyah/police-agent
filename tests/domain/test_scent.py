"""What a trail looks like when it is laid, and how it fades.

These numbers are the specification, not a design choice: the emission window is
figure 4 and the decay curve is figure 5. They are also what the opposing peer
must compute identically for a match to mean anything (Appendix He 23 voids a
game over a decay-formula mismatch), so a change here is a change to the
agreement rather than a refactor.
"""

import pytest

from tests.conftest import scent_field

# Figure 4: the 5x5 emission window around an agent, centre tau = 0.9.
FIGURE_4 = [
    [0.04, 0.14, 0.20, 0.14, 0.04],
    [0.14, 0.42, 0.62, 0.42, 0.14],
    [0.20, 0.62, 0.90, 0.62, 0.20],
    [0.14, 0.42, 0.62, 0.42, 0.14],
    [0.04, 0.14, 0.20, 0.14, 0.04],
]


class TestEmissionShape:
    def test_the_window_reproduces_the_specifications_figure(self):
        scent = scent_field()
        scent.deposit((3, 3))

        window = [
            [round(scent.intensity_at((row, col)), 2) for col in range(1, 6)] for row in range(1, 6)
        ]

        assert window == FIGURE_4

    def test_the_falloff_is_radial_and_not_square(self):
        """A diagonal neighbour is further away than an orthogonal one, and smells it."""
        scent = scent_field()
        scent.deposit((3, 3))

        assert scent.intensity_at((3, 4)) > scent.intensity_at((2, 2))

    def test_nothing_is_laid_beyond_the_agreed_field_size(self):
        scent = scent_field()
        scent.deposit((3, 3))

        assert scent.intensity_at((3, 6)) == 0.0
        assert scent.intensity_at((0, 0)) == 0.0

    def test_the_field_is_clipped_at_the_edge_of_the_board(self):
        scent = scent_field()
        scent.deposit((0, 0))

        cells = [tuple(int(part) for part in key.split(",")) for key in scent.snapshot()]

        assert scent.intensity_at((0, 0)) == 0.9
        assert all(0 <= row < 7 and 0 <= col < 7 for row, col in cells)

    def test_an_emission_below_the_agreed_floor_is_refused(self):
        with pytest.raises(ValueError, match="below the agreed minimum"):
            scent_field().deposit((3, 3), intensity=0.4)

    def test_an_even_field_would_have_no_centre_to_emit_from(self):
        with pytest.raises(ValueError, match="positive and odd"):
            scent_field(smell_grid_size=4)

    def test_a_board_must_have_cells(self):
        with pytest.raises(ValueError, match="must be positive"):
            scent_field(board_size=0)


class TestDecay:
    def test_a_trail_keeps_nine_tenths_of_its_strength_each_turn(self):
        scent = scent_field()
        scent.deposit((3, 3))

        scent.decay_all()
        assert scent.intensity_at((3, 3)) == 0.81
        scent.decay_all()
        assert scent.intensity_at((3, 3)) == 0.729

    @pytest.mark.parametrize("turns, expected", [(5, 0.53), (7, 0.43), (14, 0.21), (20, 0.11)])
    def test_the_curve_follows_the_specification_turn_by_turn(self, turns, expected):
        """Figure 5: multiplying, not subtracting, is what gives the long tail."""
        scent = scent_field()
        scent.deposit((3, 3))

        for _ in range(turns):
            scent.decay_all()

        assert round(scent.intensity_at((3, 3)), 2) == expected

    def test_a_trail_is_still_legible_at_the_end_of_a_full_length_game(self):
        scent = scent_field()
        scent.deposit((3, 3))

        for _ in range(35):  # the agreed move ceiling
            scent.decay_all()

        assert scent.intensity_at((3, 3)) > 0.0

    def test_a_trail_eventually_fades_out_instead_of_staining_the_board(self):
        """Long after any game would have ended, not during one."""
        scent = scent_field()
        scent.deposit((3, 3))

        for _ in range(50):
            scent.decay_all()

        assert scent.snapshot() == {}

    def test_standing_still_holds_the_trail_at_the_agreed_maximum(self):
        """Figure 5: an agent that stays put keeps a flat peak, it does not climb."""
        scent = scent_field()
        for _ in range(8):
            scent.emit((3, 3))

        assert scent.intensity_at((3, 3)) == 0.9
        assert all(value <= 0.9 for value in scent.snapshot().values())
