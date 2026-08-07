"""The live control bar: Start, Pause, Play, Stop, Quit, Restart.

The window opens idle. Nothing touches the network until Start is pressed, which
is what makes it usable in a demonstration: both peers can be opened, the boards
inspected, and the match begun when someone is watching.

Restart is available at every stage, mid-game included: it requests a fresh
sub-game through the control channel (`peer/control_link.py`) so the running
turn loop can abandon this one cleanly before rebuilding, rather than only
ever restarting a match that has already ended. "Bidirectional control" is
what turns that request into something the opponent also honours -- the
channel activates only once BOTH peers have checked it, so restarting alone
never binds the other side to anything it did not agree to.
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
        self.restart = tk.Button(bar, text="Restart", command=app.restart)
        self.restart.pack(side="left", padx=(8, 0))
        self.bidi_var = tk.BooleanVar(value=False)
        self.bidi_check = tk.Checkbutton(
            bar,
            text="Bidirectional control",
            variable=self.bidi_var,
            command=app.toggle_bidirectional,
        )
        self.bidi_check.pack(side="left", padx=(8, 0))

    def mark_started(self) -> None:
        """Lock Start and release the live steers. Start is not re-armable.

        A second Start would negotiate a second handshake on a runtime that has
        already agreed its terms, so the button is spent once pressed. Restart
        is different: it never re-arms this runtime, it tears it down and
        builds a fresh one, which is exactly why it stays live here too.
        """
        self.start.config(state="disabled")
        for button in (self.pause, self.play, self.stop):
            button.config(state="normal")

    def mark_finished(self) -> None:
        """The game is over: nothing is left to steer but Restart and Quit."""
        for button in (self.pause, self.play, self.stop):
            button.config(state="disabled")
