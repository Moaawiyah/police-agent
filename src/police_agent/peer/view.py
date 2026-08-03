"""A snapshot of what this peer can see, for anything watching the game.

The GUI renders a view; it does not read the runtime. That separation is not
decoration -- the runtime plays on a worker thread while Tk redraws on the main
one, so a view that held live references to `state.visited` would be iterated
while the game was still adding to it. Everything mutable is copied here, at the
moment the event fires, and what the window later draws is what was true then.

What a view may contain is also a rule, not a convenience: the police's own
truth, and a *belief* about the thief. The thief's real position is not in this
process to leak (spec ch. 2.4.2), and the heatmap is the whole point -- ch. 6.4
asks for the belief to be shown, uncertainty and all.
"""


def snapshot(runtime) -> dict:
    """Everything a watcher may know, copied out of the runtime as it stands now."""
    state = runtime.state
    return {
        "role": "police",
        "step": state.step_number,
        "position": state.position,
        "visited": frozenset(state.visited),
        "barriers": frozenset(state.barriers),
        "belief": belief_matrix(runtime.threat, state.board.size),
        "barriers_used": state.my_barriers,
        "barriers_max": runtime.barriers_max,
    }


def belief_matrix(threat, board_size: int) -> list[list[float]]:
    """The belief map as rows of probability, or a flat grid if there is no map.

    The threat estimate is a seam with several implementations (`BeliefGrid` in
    play, `PointThreat` and `UniformThreat` in tests), and only the real map can
    draw itself. A flat grid rather than an empty one keeps the renderer free of
    a special case: an even belief is a truthful picture of knowing nothing.
    """
    as_matrix = getattr(threat, "as_matrix", None)
    if as_matrix is None:
        flat = 1.0 / (board_size * board_size)
        return [[flat] * board_size for _ in range(board_size)]
    return as_matrix()
