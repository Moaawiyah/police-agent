"""Playback actions for :class:`police_agent.gui.replay.ReplayApp`."""

from police_agent.sdk.replay import frozen_message, move_labels, verify_record

MIN_TICK_MS = 50


def advance(app) -> None:
    """Apply one more recorded step, or announce the replay is done."""
    total = app._total_steps()
    if app._index >= total:
        app._playing = False
        app._window.set_turn(
            False, f"REPLAY DONE: {app._result} - winner {str(app._winner).upper()}"
        )
        return
    index = app._index
    app._apply_my_step(index)
    app._apply_opponent_step(index)
    app._render(index, total)
    app._index += 1


def apply_my_step(app, index: int) -> None:
    """Fold this peer's own logged step into the visited/barrier trail and panel labels."""
    if index >= len(app._my_log):
        return
    entry = app._my_log[index]
    app._visited.add(tuple(entry["position"]))
    if entry.get("barrier"):
        app._barriers.add(tuple(entry["barrier"]))
    record = app._records[index] if index < len(app._records) else {}
    for key, value in move_labels(record, verify_record(app._records, index)).items():
        app._window.set_label(key, value)


def apply_opponent_step(app, index: int) -> None:
    """Advance the belief filter with the opponent's step and update the hint label."""
    if index >= len(app._history):
        return
    message = app._history[index]
    if message.get("barrier_placed"):
        app._barriers.add(tuple(message["barrier_placed"]))
    app._belief.diffuse(app._barriers)
    app._belief.observe_smell(message.get("smell_grid"))
    app._window.set_label("hint_in", f"step {index + 1}: {message.get('hint') or '(silent)'}")


def render(app, index: int, total: int) -> None:
    """Draw the current step and the status line under it."""
    mine, theirs = len(app._my_log), len(app._opponent)
    app._window.render(
        {
            "role": app._role,
            "step": index + 1,
            "position": tuple(app._my_log[min(index, mine - 1)]["position"]) if mine else None,
            "visited": app._visited,
            "barriers": app._barriers,
            "belief": app._belief.as_matrix(),
            "opponent_position": tuple(app._opponent[min(index, theirs - 1)])
            if theirs
            else None,
            "opponent_role": "thief",
            "message": frozen_message(index, mine, theirs),
        }
    )
    both = "both agents shown" if app._opponent else "opponent log not supplied"
    passed = "PASSED" if app._audit.get("passed") else "FAILED"
    app._window.set_label("status", f"step {index + 1}/{total} | audit {passed} | {both}")


def restart(app) -> None:
    """Reset all replay state and redraw the empty board."""
    app._reset_state()
    app._playing = False
    render_empty(app)
    app._window.set_turn(False, "RESTARTED - press Play")


def render_empty(app) -> None:
    """Draw the board with nothing on it yet."""
    app._window.render(
        {
            "role": app._role,
            "step": 0,
            "position": None,
            "visited": set(),
            "barriers": set(),
            "belief": app._belief.as_matrix(),
        }
    )


def goto(app, step: int) -> None:
    """Replay from the start up to `step`."""
    app._reset_state()
    for _ in range(max(1, min(step, app._total_steps()))):
        app.advance()


def toggle(app) -> None:
    """Start or pause auto-play."""
    app._playing = not app._playing
    if app._playing:
        app._tick()


def tick(app) -> None:
    """One auto-play frame, rescheduled at the current speed."""
    if not app._playing:
        return
    app.advance()
    app._window.root.after(max(MIN_TICK_MS, int(app._window.speed.get() * 1000)), app._tick)


def run(app) -> None:
    """Show the window and block until it closes."""
    app._window.set_turn(False, "REPLAY - press Play")
    app._window.root.mainloop()
