"""Colours and geometry for the board, kept free of Tk so they can be tested.

Every number the canvas draws with is here, and none of it imports `tkinter`.
That is deliberate: a test that checks the heatmap actually gets *hotter* where
the belief is higher should not need a display, a window manager, or a Tcl
runtime to run.
"""

CELL_PIXELS = 52
ROLE_COLORS = {"police": "#2980b9", "thief": "#e67e22"}
UNKNOWN_ROLE_COLOR = "#555555"

GRID_LINE = "#cccccc"
VISITED_DOT = "#b0bec5"
BARRIER_FILL = "#263238"
BANNER_FILL = "#ffe082"
BANNER_TEXT = "#5d4037"

# How dark the hottest cell gets. Below 1.0 the peak stays legible against the
# black barrier squares and the white agent lettering drawn on top of it.
MAX_SATURATION = 0.8


def heat_color(probability: float, peak: float) -> str:
    """White through red, scaled against the current peak rather than an absolute.

    Relative scaling is what makes the map readable at all. A belief over 49
    cells starts at 0.02 everywhere and rarely passes 0.3, so an absolute scale
    would render every interesting state as an almost uniform white. Against the
    peak, the most likely cell is always fully saturated and the picture shows
    the *shape* of the belief -- which is the thing a viewer is reading.
    """
    if peak <= 0:
        return "#ffffff"
    level = min(1.0, max(0.0, probability / peak))
    # Rounded, not truncated: `1 - 0.8 * 1.0` lands a hair under 0.2 in binary
    # floating point, and truncating would make the peak colour depend on that.
    green_blue = round(255 * (1 - MAX_SATURATION * level))
    return f"#ff{green_blue:02x}{green_blue:02x}"


def role_color(role: str) -> str:
    """The disc colour for an agent, falling back to grey for an unnamed role."""
    return ROLE_COLORS.get(role, UNKNOWN_ROLE_COLOR)


def cell_rect(row: int, col: int) -> tuple[int, int, int, int]:
    """Pixel bounds of one cell: `(x0, y0, x1, y1)`, row-major like the board."""
    x0, y0 = col * CELL_PIXELS, row * CELL_PIXELS
    return x0, y0, x0 + CELL_PIXELS, y0 + CELL_PIXELS
