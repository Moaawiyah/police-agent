"""BoardView: the canvas showing one peer's world -- and what it merely believes.

Four layers, drawn bottom to top: the belief heatmap over every cell, the trail
of cells this peer has occupied, the declared barriers, then the agents.

What is *not* drawn matters as much. In live play the opponent's true position
is not on this board, because it is not in this process to draw (spec ch. 2.4.2)
-- the red cloud is the entire answer to "where is the thief", and its vagueness
is the honest picture. Replay is the exception: both logs have been revealed by
then, so the second marker can finally appear.
"""

import tkinter as tk

from police_agent.gui.palette import (
    BANNER_FILL,
    BANNER_TEXT,
    BARRIER_FILL,
    CELL_PIXELS,
    GRID_LINE,
    VISITED_DOT,
    cell_rect,
    heat_color,
    role_color,
)

BANNER_HEIGHT = 22
VISITED_INSET = 21
BARRIER_INSET = 4
MY_INSET = 8
OPPONENT_INSET = 14


class BoardView(tk.Canvas):
    """A square grid canvas for one peer's view of the board."""

    def __init__(self, parent, board_size: int) -> None:
        self.board_size = board_size
        side = board_size * CELL_PIXELS
        super().__init__(
            parent,
            width=side,
            height=side,
            bg="white",
            highlightthickness=1,
            highlightbackground="#888888",
        )

    def render(self, view: dict) -> None:
        """Redraw everything from one view snapshot. Nothing is drawn incrementally.

        A full redraw per step is not an optimisation worth making: the board is
        7x7, and a canvas that accumulated deltas would drift out of step with
        the snapshot the moment one event was dropped.
        """
        self.delete("all")
        self._draw_heatmap(view["belief"])
        for cell in view["visited"]:
            self._draw_dot(cell, VISITED_INSET, VISITED_DOT)
        for cell in view["barriers"]:
            self._draw_square(cell, BARRIER_INSET, BARRIER_FILL)
        opponent = view.get("opponent_position")
        if opponent is not None:
            self._draw_agent(opponent, view.get("opponent_role", "thief"), OPPONENT_INSET)
        if view.get("position") is not None:
            self._draw_agent(view["position"], view["role"], MY_INSET)
        if view.get("message"):
            self._draw_banner(view["message"])

    def _draw_heatmap(self, belief: list[list[float]]) -> None:
        peak = max((cell for row in belief for cell in row), default=0.0)
        for row in range(self.board_size):
            for col in range(self.board_size):
                self.create_rectangle(
                    *cell_rect(row, col),
                    outline=GRID_LINE,
                    fill=heat_color(belief[row][col], peak),
                )

    def _draw_dot(self, cell, inset: int, fill: str) -> None:
        x0, y0, x1, y1 = cell_rect(*cell)
        self.create_oval(x0 + inset, y0 + inset, x1 - inset, y1 - inset, fill=fill, outline="")

    def _draw_square(self, cell, inset: int, fill: str) -> None:
        x0, y0, x1, y1 = cell_rect(*cell)
        self.create_rectangle(x0 + inset, y0 + inset, x1 - inset, y1 - inset, fill=fill, outline="")

    def _draw_agent(self, cell, role: str, inset: int) -> None:
        x0, y0, x1, y1 = cell_rect(*cell)
        self.create_oval(
            x0 + inset,
            y0 + inset,
            x1 - inset,
            y1 - inset,
            fill=role_color(role),
            outline="black",
            width=2,
        )
        self.create_text(
            (x0 + x1) // 2,
            (y0 + y1) // 2,
            text=role[:1].upper(),
            fill="white",
            font=("Helvetica", 14, "bold"),
        )

    def _draw_banner(self, message: str) -> None:
        """A strip across the top for something the board itself cannot show."""
        width = self.board_size * CELL_PIXELS
        self.create_rectangle(0, 0, width, BANNER_HEIGHT, fill=BANNER_FILL, outline="")
        self.create_text(
            width // 2,
            BANNER_HEIGHT // 2,
            text=message,
            fill=BANNER_TEXT,
            font=("Helvetica", 10, "bold"),
        )
