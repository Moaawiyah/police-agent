"""Drawing one view dict to a PIL image, with no display involved."""

from PIL import Image

from police_agent.gui.export_render import render_frame
from police_agent.gui.palette import CELL_PIXELS

BOARD = 4
FLAT = [[1.0 / (BOARD * BOARD)] * BOARD for _ in range(BOARD)]


def _view(**overrides) -> dict:
    base = {
        "role": "police",
        "position": (0, 0),
        "visited": set(),
        "barriers": set(),
        "belief": FLAT,
        "opponent_position": None,
        "opponent_role": "thief",
    }
    return {**base, **overrides}


def test_the_frame_is_one_cell_per_board_square():
    frame = render_frame(_view(), BOARD)

    assert isinstance(frame, Image.Image)
    assert frame.size == (BOARD * CELL_PIXELS, BOARD * CELL_PIXELS)


def test_a_hotter_cell_renders_more_saturated_red():
    belief = [row[:] for row in FLAT]
    belief[2][2] = 0.9
    frame = render_frame(_view(belief=belief), BOARD)

    hot_pixel = frame.getpixel(
        (2 * CELL_PIXELS + CELL_PIXELS // 2, 2 * CELL_PIXELS + CELL_PIXELS // 2)
    )
    cold_pixel = frame.getpixel((0, 0))

    assert hot_pixel[1] < cold_pixel[1]  # heat_color darkens green/blue as belief rises


def test_the_opponent_marker_only_appears_when_a_position_is_given():
    without = render_frame(_view(), BOARD)
    with_opponent = render_frame(_view(opponent_position=(3, 3)), BOARD)

    assert without.tobytes() != with_opponent.tobytes()
