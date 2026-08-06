"""PeerWindow: the chrome both the live view and the replay player sit inside.

A turn banner across the top, the board on the left, a panel of labelled facts
on the right, and a speed slider under it. Live and replay share it because they
are showing the same thing at different times -- one from a running game, one
from a log -- and two windows that drifted apart would make a screenshot of the
replay useless as evidence about the live run (spec ch. 9.4.2 asks for both).

The panel is a flat dict of labels rather than named attributes so that a caller
can set one by key without this class knowing what any of them mean.
"""

import tkinter as tk

from police_agent.gui.board_view import BoardView
from police_agent.shared.version import CODE_VERSION, PROJECT_TITLE, REPOSITORY_URL

MY_TURN_COLOR = "#2ecc71"
WAITING_COLOR = "#95a5a6"

# (key, caption) in display order. No live-ticking counter mid-game -- the
# shipped verbal layer is a free local Ollama model, so there is no per-call
# budget worth watching turn by turn -- but the total (Appendix He 54) is
# worth showing once the match ends, alongside the audit line.
PANEL_ROWS = (
    ("step", "Step"),
    ("mode", "Verbal mode"),
    ("model", "Model"),
    ("barriers", "Barriers used"),
    ("hint_in", "Thief says"),
    ("hint_out", "My reply"),
    ("verdict", "Why I moved"),
    ("commit", "My commit (sealed)"),
    ("reliability", "Thief reliability"),
    ("status", "Status"),
    ("tokens", "Tokens used"),
)


class PeerWindow:
    """One peer's window: banner, board, fact panel, speed slider."""

    def __init__(self, title: str, board_size: int, speed: float) -> None:
        self.root = tk.Tk()
        self.root.title(title)
        self.banner = tk.Label(
            self.root,
            text="WAITING...",
            bg=WAITING_COLOR,
            fg="white",
            font=("Helvetica", 14, "bold"),
            pady=6,
        )
        self.banner.pack(fill="x")
        body = tk.Frame(self.root)
        body.pack(padx=8, pady=8)
        self.board = BoardView(body, board_size)
        self.board.pack(side="left")
        self.labels: dict[str, tk.Label] = {}
        self.speed = tk.DoubleVar(value=speed)
        self._build_panel(body)

    def _build_panel(self, body) -> None:
        panel = tk.Frame(body)
        panel.pack(side="left", fill="y", padx=(10, 0))
        for key, caption in PANEL_ROWS:
            tk.Label(panel, text=f"{caption}:", font=("Helvetica", 9, "bold"), anchor="w").pack(
                fill="x"
            )
            self.labels[key] = tk.Label(panel, text="-", anchor="w", wraplength=300, justify="left")
            self.labels[key].pack(fill="x", pady=(0, 6))
        tk.Label(
            panel,
            text="Seconds per step\n(0 = as fast as the opponent allows):",
            font=("Helvetica", 9, "bold"),
            anchor="w",
            justify="left",
        ).pack(fill="x")
        tk.Scale(
            panel, from_=0.0, to=10.0, resolution=0.1, orient="horizontal", variable=self.speed
        ).pack(fill="x")

    def add_menu(self, about: dict) -> None:
        """A Help menu with an About box naming the code version and the spec facts."""
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=lambda: self._show_about(about))
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def _show_about(self, about: dict) -> None:
        top = tk.Toplevel(self.root)
        top.title(f"About - {PROJECT_TITLE}")
        header = f"{PROJECT_TITLE}\nCode version: v{CODE_VERSION}\n{REPOSITORY_URL}"
        tk.Label(
            top,
            text=header,
            justify="left",
            anchor="w",
            font=("Helvetica", 11, "bold"),
            padx=14,
            pady=(12, 6),
        ).pack(fill="x")
        details = "\n".join(f"{key}: {value}" for key, value in about.items())
        tk.Label(
            top,
            text=details,
            justify="left",
            anchor="w",
            font=("Courier", 9),
            padx=14,
            pady=(0, 10),
        ).pack(fill="x")
        tk.Button(top, text="Close", command=top.destroy).pack(pady=(0, 10))

    def set_turn(self, mine: bool, text: str | None = None) -> None:
        """Colour the banner. Green means this peer owes the opponent a move."""
        self.banner.config(
            bg=MY_TURN_COLOR if mine else WAITING_COLOR,
            text=text or ("MY TURN - deciding..." if mine else "WAITING for the thief..."),
        )

    def set_label(self, key: str, value: str) -> None:
        self.labels[key].config(text=value)

    def render(self, view: dict) -> None:
        """Draw one view snapshot and update the facts that come with it."""
        self.board.render(view)
        self.set_label("step", str(view["step"]))
        if "barriers_used" in view:
            self.set_label("barriers", f"{view['barriers_used']} / {view['barriers_max']}")
