"""Reconstructing one view dict per step from a saved match log, headlessly.

Same shape `BoardView.render` draws from (`gui/replay_actions.py::render`),
built the same way the replay player walks a log -- so this and the replay
window can never quietly show two different pictures of the same match.

Prefers the log's own recorded `belief_log` (police-only, byte-accurate: see
`peer/runtime_loop.py`) over recomputing the filter from `history`, and falls
back to recomputing for older logs that predate it. The fallback filter is
still advanced every step regardless, so a log with only a partial
`belief_log` never desyncs mid-replay.
"""

from police_agent.gui.replay_data import frozen_message, normalize_log, opponent_positions
from police_agent.strategy.belief import BeliefGrid

__all__ = ["build_views"]


def build_views(
    log_data: dict, opponent_log: dict | None, board_size: int, smell_trust: float
) -> list[dict]:
    view = normalize_log(log_data)
    my_log, history = view["my_log"], view["history"]
    opponent = opponent_positions(opponent_log)
    recorded = {
        entry["step"]: entry["belief"] for entry in view.get("belief_log") or [] if "step" in entry
    }

    belief = BeliefGrid(board_size, smell_trust)
    visited: set = set()
    barriers: set = set()
    frames: list[dict] = []
    total = max(len(my_log), len(history), len(opponent))
    for index in range(total):
        matrix = _advance(belief, my_log, history, visited, barriers, index, recorded)
        frames.append(_frame(view["role"], my_log, opponent, visited, barriers, matrix, index))
    return frames


def _advance(belief, my_log, history, visited, barriers, index, recorded) -> list[list[float]]:
    if index < len(my_log):
        entry = my_log[index]
        visited.add(tuple(entry["position"]))
        if entry.get("barrier"):
            barriers.add(tuple(entry["barrier"]))
    if index >= len(history):
        return belief.as_matrix()
    message = history[index]
    belief.diffuse()
    belief.observe_smell(message.get("smell_grid"))
    if message.get("barrier_placed"):
        barriers.add(tuple(message["barrier_placed"]))
    step = message.get("step", index + 1)
    return recorded.get(step, belief.as_matrix())


def _frame(role, my_log, opponent, visited, barriers, matrix, index) -> dict:
    mine, theirs = len(my_log), len(opponent)
    return {
        "role": role,
        "step": index + 1,
        "position": tuple(my_log[min(index, mine - 1)]["position"]) if mine else None,
        "visited": set(visited),
        "barriers": set(barriers),
        "belief": matrix,
        "opponent_position": tuple(opponent[min(index, theirs - 1)]) if theirs else None,
        "opponent_role": "thief",
        "message": frozen_message(index, mine, theirs),
    }
