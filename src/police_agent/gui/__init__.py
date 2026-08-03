"""The GUI layer: a live window and a replay player, holding no game logic.

Adapted from the course reference implementation's `gui/` package (see
docs/PLAN.md, step 8). What was taken is the *shape*: a shared window chrome
over a canvas that draws one peer's truth plus its belief heatmap, a live app
that mirrors a runtime event stream from a worker thread, and a replay player
that feeds a saved log back through the pure domain and re-verifies each commit
as it goes. What was rewritten is everything below that, because our runtime
publishes different events, our config names different things, and the reference
is licensed for reading, not for copying.

Nothing here decides anything about the game. The live app renders the views the
runtime hands it; the replay app replays a log through the same `BeliefGrid` the
agent used. Both reach the agent only through `police_agent.sdk`.

Tk on Windows under a `uv` virtualenv is the one environment quirk worth
handling here: the interpreter looks for the Tcl runtime inside the venv while
the base installation keeps it under `<base>/tcl`, so a window that would open
from the system Python fails from the venv with an obscure init error.
"""

import os
import sys
from pathlib import Path

TCL_SUBDIRECTORIES = (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6"))


def point_tk_at_the_base_interpreter() -> None:
    """Fill in the Tcl/Tk paths when the venv has none, leaving any set value alone."""
    base = Path(sys.base_prefix)
    for variable, subdirectory in TCL_SUBDIRECTORIES:
        candidate = base / "tcl" / subdirectory
        if variable not in os.environ and candidate.is_dir():
            os.environ[variable] = str(candidate)


point_tk_at_the_base_interpreter()
