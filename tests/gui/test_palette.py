"""The heatmap colour scale: hotter must mean more likely, and readably so."""

from police_agent.gui.palette import CELL_PIXELS, cell_rect, heat_color, role_color


def test_the_peak_cell_is_the_reddest():
    assert heat_color(1.0, 1.0) == "#ff3333"


def test_an_empty_cell_is_white():
    assert heat_color(0.0, 1.0) == "#ffffff"


def test_colour_is_relative_to_the_peak_not_absolute():
    """A belief over 49 cells rarely exceeds 0.3, so an absolute scale would
    render every interesting state as an almost uniform white."""
    assert heat_color(0.05, 0.05) == heat_color(0.9, 0.9)


def test_more_probable_cells_are_darker():
    cool = heat_color(0.2, 1.0)
    warm = heat_color(0.8, 1.0)

    assert int(warm[3:5], 16) < int(cool[3:5], 16)


def test_a_belief_that_has_collapsed_to_nothing_draws_blank():
    """Before any scent arrives the peak can be zero, and dividing by it would
    raise rather than draw an empty board."""
    assert heat_color(0.0, 0.0) == "#ffffff"


def test_probability_above_the_peak_is_clamped():
    assert heat_color(5.0, 1.0) == heat_color(1.0, 1.0)


def test_the_two_roles_are_told_apart_and_an_unknown_one_is_grey():
    assert role_color("police") != role_color("thief")
    assert role_color("referee") == "#555555"


def test_cells_are_laid_out_row_major_like_the_board():
    """Row is the vertical axis: cell (1, 0) sits below (0, 0), not beside it."""
    assert cell_rect(0, 0) == (0, 0, CELL_PIXELS, CELL_PIXELS)
    assert cell_rect(1, 0)[1] == CELL_PIXELS
    assert cell_rect(0, 1)[0] == CELL_PIXELS
