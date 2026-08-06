"""Per-step view reconstruction from a saved log, headlessly."""

from police_agent.gui.export_frames import build_views

BOARD = 5
TRUST = 4.0


def _log(my_log, history, belief_log=None):
    return {"role": "police", "my_log": my_log, "history": history, "belief_log": belief_log or []}


def test_one_frame_per_step_of_the_longer_track():
    log = _log(
        my_log=[{"position": [0, 0]}, {"position": [1, 0]}],
        history=[{"step": 1, "smell_grid": {}}],
    )

    frames = build_views(log, None, BOARD, TRUST)

    assert len(frames) == 2
    assert [frame["position"] for frame in frames] == [(0, 0), (1, 0)]


def test_visited_and_barriers_accumulate_across_steps():
    log = _log(
        my_log=[{"position": [0, 0], "barrier": [2, 2]}, {"position": [1, 0]}],
        history=[],
    )

    frames = build_views(log, None, BOARD, TRUST)

    assert frames[1]["visited"] == {(0, 0), (1, 0)}
    assert frames[1]["barriers"] == {(2, 2)}


def test_a_recorded_belief_is_used_verbatim_instead_of_recomputed():
    """The whole point of belief_log: a new-format log replays with the actual
    recorded posterior rather than a recomputation that could drift from it."""
    recorded = [[0.0] * BOARD for _ in range(BOARD)]
    recorded[3][3] = 1.0
    log = _log(
        my_log=[{"position": [0, 0]}],
        history=[{"step": 1, "smell_grid": {"0,0": 0.9}}],
        belief_log=[{"step": 1, "belief": recorded}],
    )

    frames = build_views(log, None, BOARD, TRUST)

    assert frames[0]["belief"] == recorded


def test_an_older_log_without_belief_log_still_recomputes_a_belief():
    log = _log(
        my_log=[{"position": [0, 0]}],
        history=[{"step": 1, "smell_grid": {"0,0": 0.9}}],
    )

    frames = build_views(log, None, BOARD, TRUST)

    cells = [(row, col) for row in range(BOARD) for col in range(BOARD)]
    peak_cell = max(cells, key=lambda cell: frames[0]["belief"][cell[0]][cell[1]])
    assert peak_cell == (0, 0)  # the only cell that ever smelled of anything


def test_the_opponent_position_appears_only_when_its_log_is_supplied():
    log = _log(my_log=[{"position": [0, 0]}], history=[])
    opponent_log = _log(my_log=[{"position": [3, 3]}], history=[])

    without = build_views(log, None, BOARD, TRUST)
    with_opponent = build_views(log, opponent_log, BOARD, TRUST)

    assert without[0]["opponent_position"] is None
    assert with_opponent[0]["opponent_position"] == (3, 3)
