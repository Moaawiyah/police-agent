"""The predict half of the filter: what happens to a belief when the thief moves.

Diffusing is the step that makes the police *less* sure, and it is the easiest
one to get subtly wrong -- spreading mass somewhere the thief could not reach
would have the police confidently chasing an impossible cell.
"""

from police_agent.strategy.belief import BeliefGrid


def total(belief: BeliefGrid) -> float:
    """Rounded past float noise: the invariant is "sums to one"."""
    return round(sum(sum(row) for row in belief.as_matrix()), 9)


def test_mass_spreads_only_the_way_the_thief_may_actually_move():
    """A diagonal is two orthogonal steps, so it must not gain mass in one turn."""
    belief = BeliefGrid(7)
    belief.observe_smell({"3,3": 0.9})

    belief.diffuse()
    matrix = belief.as_matrix()

    assert matrix[2][3] > matrix[2][2]  # the orthogonal neighbour beat the diagonal
    assert matrix[3][2] > matrix[2][2]


def test_prediction_blurs_a_belief_rather_than_sharpening_it():
    belief = BeliefGrid(7)
    belief.observe_smell({"3,3": 0.9})
    peak = belief.as_matrix()[3][3]

    belief.diffuse()

    assert belief.as_matrix()[3][3] < peak


def test_a_ruled_out_cell_has_no_mass_to_spread():
    belief = BeliefGrid(7)
    belief.exclude((3, 3))

    belief.diffuse()

    assert total(belief) == 1.0


def test_a_barrier_stops_mass_from_spreading_through_it():
    """A blocked neighbour gets none of the concentrated mass, only ambient leak."""
    belief = BeliefGrid(7)
    belief.observe_smell({"3,3": 0.9})

    belief.diffuse(barriers={(2, 3)})
    matrix = belief.as_matrix()

    assert matrix[2][3] < matrix[4][3]  # the open, symmetric neighbour got it instead


def test_mass_is_conserved_even_when_every_target_is_blocked():
    """Walled in on every side, including staying put: mass has nowhere to go but stay."""
    belief = BeliefGrid(7)
    belief.observe_smell({"3,3": 0.9})
    barriers = {(3, 3), (2, 3), (4, 3), (3, 2), (3, 4)}

    belief.diffuse(barriers=barriers)

    assert total(belief) == 1.0
    assert belief.as_matrix()[3][3] > 0.0


def test_ties_resolve_the_same_way_every_time():
    """The strategy above this is deterministic and needs a deterministic input."""
    answers = set()
    for grid in ({"1,1": 0.5, "2,2": 0.5}, {"2,2": 0.5, "1,1": 0.5}):
        belief = BeliefGrid(7)
        belief.observe_smell(grid)
        answers.add(belief.most_likely())

    assert answers == {(1, 1)}
