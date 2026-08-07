"""The live control bar: Start, Pause, Play, Stop, Quit, Restart.

The window opens idle. Nothing touches the network until Start is pressed, which
is what makes it usable in a demonstration: both peers can be opened, the boards
inspected, and the match begun when someone is watching.

Every button here steers *this* peer and only this peer, and Restart is no
exception: it plays a brand-new local sub-game against the same opponent, not a
signal sent to it. There is no channel to coordinate a restart over -- the
protocol carries turns and audits, and a control message the thief never agreed
to read would be a pause (or a restart) that only one side observed.
"""

import tkinter as tk


class LiveControls:
    """Owns the control-bar widgets and the enable/disable states between them."""

    def __init__(self, root, app) -> None:
        bar = tk.Frame(root)
        bar.pack(pady=(0, 6))
        self.start = tk.Button(bar, text="Start", command=app.start)
        self.start.pack(side="left")
        self.pause = tk.Button(bar, text="Pause", command=app.pause, state="disabled")
        self.pause.pack(side="left", padx=(8, 0))
        self.play = tk.Button(bar, text="Play", command=app.play, state="disabled")
        self.play.pack(side="left")
        self.stop = tk.Button(bar, text="Stop", command=app.stop, state="disabled")
        self.stop.pack(side="left")
        self.quit = tk.Button(bar, text="Quit", command=app.quit, state="normal")
        self.quit.pack(side="left", padx=(8, 0))
        self.restart = tk.Button(bar, text="Restart", command=app.restart, state="disabled")
        self.restart.pack(side="left", padx=(8, 0))

    def mark_started(self) -> None:
        """Lock Start and release the live steers. Start is not re-armable.

        A second Start would negotiate a second handshake on a runtime that has
        already agreed its terms, so the button is spent once pressed. Restart
        exists for exactly this reason: it builds a fresh runtime rather than
        re-arming this one, so it locks here too -- there is nothing to restart
        until the sub-game it would replace has actually finished.
        """
        self.start.config(state="disabled")
        self.restart.config(state="disabled")
        for button in (self.pause, self.play, self.stop):
            button.config(state="normal")

    def mark_finished(self) -> None:
        """The game is over: nothing is left to steer, but a restart now makes sense."""
        for button in (self.pause, self.play, self.stop):
            button.config(state="disabled")
        self.restart.config(state="normal")
