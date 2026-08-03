"""The view snapshot: what a watcher is handed, and what it must not share."""

from police_agent.domain.own_state import OwnGameState
from police_agent.peer.view import belief_matrix, snapshot
from police_agent.strategy.belief import BeliefGrid
from police_agent.strategy.threat import UniformThreat


class FakeRuntime:
    """Just enough runtime for a snapshot: its own state and a threat estimate."""

    def __init__(self, threat=None, board_size: int = 4) -> None:
        self.state = OwnGameState((0, 0), board_size)
        self.threat = threat or BeliefGrid(board_size)
        self.barriers_max = 3


def test_the_snapshot_reports_this_peers_own_truth():
    runtime = FakeRuntime()

    view = snapshot(runtime)

    assert view["role"] == "police"
    assert view["position"] == (0, 0)
    assert view["visited"] == {(0, 0)}
    assert (view["barriers_used"], view["barriers_max"]) == (0, 3)


def test_the_snapshot_never_carries_the_thiefs_position():
    """It cannot: the police does not hold one. Only a belief may be published."""
    view = snapshot(FakeRuntime())

    assert "opponent_position" not in view
    assert "thief" not in repr(view)


def test_the_snapshot_is_a_copy_the_game_cannot_change_underneath_it():
    """The GUI draws on the main thread while the game plays on another, so a
    live reference to `visited` would be iterated as it was being added to."""
    runtime = FakeRuntime()
    view = snapshot(runtime)

    runtime.state.visited.add((3, 3))
    runtime.state.barriers.add((2, 2))

    assert view["visited"] == {(0, 0)}
    assert view["barriers"] == frozenset()


def test_the_belief_map_draws_itself_when_there_is_one():
    belief = BeliefGrid(3)
    belief.observe_smell({"1,1": 0.9})

    matrix = belief_matrix(belief, 3)

    assert matrix == belief.as_matrix()
    assert matrix[1][1] == max(cell for row in matrix for cell in row)


def test_a_threat_estimate_with_no_map_reads_as_knowing_nothing():
    """`UniformThreat` has no `as_matrix`, and a flat grid is the honest picture
    of it -- an empty one would make the renderer carry a special case."""
    matrix = belief_matrix(UniformThreat(2), 2)

    assert matrix == [[0.25, 0.25], [0.25, 0.25]]
