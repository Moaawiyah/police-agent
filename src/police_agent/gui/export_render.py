"""Drawing one view dict to a PIL image -- the headless twin of `board_view.py`.

Same four layers, same order, and the same colours from `palette.py`, so an
exported frame and the live/replay window can never quietly drift apart. No
`tkinter` import anywhere in this module: it is what lets export run with no
display, over SSH or in CI.
"""

from PIL import Image, ImageDraw

from police_agent.gui.palette import (
    BARRIER_FILL,
    CELL_PIXELS,
    GRID_LINE,
    VISITED_DOT,
    cell_rect,
    heat_color,
    role_color,
)

VISITED_INSET = 21
BARRIER_INSET = 4
MY_INSET = 8
OPPONENT_INSET = 14

__all__ = ["render_frame"]


def render_frame(view: dict, board_size: int) -> Image.Image:
    """Draw one view dict to a PIL image, the same four layers `board_view.py` draws."""
    side = board_size * CELL_PIXELS
    image = Image.new("RGB", (side, side), "white")
    draw = ImageDraw.Draw(image)
    _draw_heatmap(draw, view["belief"], board_size)
    for cell in view["visited"]:
        _draw_dot(draw, cell, VISITED_INSET, VISITED_DOT)
    for cell in view["barriers"]:
        _draw_square(draw, cell, BARRIER_INSET, BARRIER_FILL)
    opponent = view.get("opponent_position")
    if opponent is not None:
        _draw_agent(draw, opponent, view.get("opponent_role", "thief"), OPPONENT_INSET)
    if view.get("position") is not None:
        _draw_agent(draw, view["position"], view["role"], MY_INSET)
    return image


def _draw_heatmap(draw: ImageDraw.ImageDraw, belief: list[list[float]], board_size: int) -> None:
    peak = max((cell for row in belief for cell in row), default=0.0)
    for row in range(board_size):
        for col in range(board_size):
            draw.rectangle(
                cell_rect(row, col), fill=heat_color(belief[row][col], peak), outline=GRID_LINE
            )


def _draw_dot(draw: ImageDraw.ImageDraw, cell, inset: int, fill: str) -> None:
    x0, y0, x1, y1 = cell_rect(*cell)
    draw.ellipse((x0 + inset, y0 + inset, x1 - inset, y1 - inset), fill=fill)


def _draw_square(draw: ImageDraw.ImageDraw, cell, inset: int, fill: str) -> None:
    x0, y0, x1, y1 = cell_rect(*cell)
    draw.rectangle((x0 + inset, y0 + inset, x1 - inset, y1 - inset), fill=fill)


def _draw_agent(draw: ImageDraw.ImageDraw, cell, role: str, inset: int) -> None:
    x0, y0, x1, y1 = cell_rect(*cell)
    draw.ellipse(
        (x0 + inset, y0 + inset, x1 - inset, y1 - inset),
        fill=role_color(role),
        outline="black",
        width=2,
    )
    draw.text(((x0 + x1) // 2, (y0 + y1) // 2), role[:1].upper(), fill="white", anchor="mm")
