"""The replay control bar: Play/Pause, Step, Restart, and jump-to-step.

Separate from `replay.py` so that file is left holding only the stepping and the
rendering. Wired directly to the app's methods rather than to callbacks it is
handed, because there is exactly one app this bar is ever attached to and an
indirection would only hide which button does what.
"""

import tkinter as tk

MAX_STEP = 9999


def build_controls(app, root) -> None:
    """Attach the bar to `root`, wired to `app`'s stepping methods."""
    bar = tk.Frame(root)
    bar.pack(pady=(0, 8))
    tk.Button(bar, text="Play / Pause", command=app.toggle).pack(side="left")
    tk.Button(bar, text="Step >", command=app.advance).pack(side="left", padx=6)
    tk.Button(bar, text="Restart", command=app.restart).pack(side="left")
    tk.Label(bar, text="  Go to step:").pack(side="left")
    step = tk.StringVar(value="1")
    tk.Spinbox(bar, from_=1, to=MAX_STEP, width=5, textvariable=step).pack(side="left")
    tk.Button(bar, text="Go", command=lambda: app.goto(as_step(step.get()))).pack(
        side="left", padx=6
    )


def as_step(text: str, default: int = 1) -> int:
    """A spinbox's text as a step number. Anything unreadable means step one.

    The widget is editable, so this really does receive whatever was typed into
    it; refusing to parse is not an error worth interrupting a replay for.
    """
    try:
        return int(text)
    except (TypeError, ValueError):
        return default
