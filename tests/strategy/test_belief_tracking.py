"""Does the belief track a moving thief, or smear into a comet-tail behind it?

`most_likely()` alone cannot see this: diffuse() only ever spreads mass one
cell per turn, so even a correct filter lags a continuously-moving thief by
design. What distinguishes a well-shaped belief from a stale, trail-shaped one
is *where the probability mass sits* -- concentrated near the thief's current
cell, or smeared across cells it visited many turns ago. Both scenarios below
feed a real `ScentField`'s output (not hand-typed intensities) into a
`BeliefGrid`, comparing the shipped defaults (`DEFAULT_SMELL_POWER`,
`DEFAULT_LEAK`) against the old linear/no-leak filter (`smell_power=1.0,
leak=0.0`).
"""

from police_agent.strategy.belief import BeliefGrid
from tests.conftest import scent_field

BOARD_SIZE = 7


def _sprint_east_then_south() -> list[tuple[int, int]]:
    """A hard case: the thief moves every single turn, four steps east then a
    direction change, four steps south -- no pause for the filter to lock on."""
    path = [(1, 1)]
    for _ in range(4):
        row, col = path[-1]
        path.append((row, col + 1))
    for _ in range(4):
        row, col = path[-1]
        path.append((row + 1, col))
    return path


def _linger_then_move() -> list[tuple[int, int]]:
    """A realistic case: the thief sits still long enough to be pinned down,
    then moves off with a direction change partway."""
    path = [(3, 3)]
    for _ in range(3):
        path.append(path[-1])
    for _ in range(2):
        row, col = path[-1]
        path.append((row, col + 1))
    for _ in range(2):
        row, col = path[-1]
        path.append((row + 1, col))
    return path


def _mass_near(matrix, position, radius: int = 2) -> float:
    """Probability within `radius` Manhattan steps of `position` -- roughly the
    scent kernel's own footprint, so this isn't just re-measuring the kernel."""
    return sum(
        matrix[row][col]
        for row in range(BOARD_SIZE)
        for col in range(BOARD_SIZE)
        if abs(row - position[0]) + abs(col - position[1]) <= radius
    )


def _mass_on(matrix, cells) -> float:
    return sum(matrix[row][col] for row, col in set(cells))


def test_the_default_filter_beats_linear_no_leak_on_a_hard_continuous_chase():
    """Even where diffuse()'s one-cell-a-turn limit keeps both filters behind
    a thief that never stops moving, the default stays closer to the thief and
    lighter on the stale trail than the old filter, every turn checked."""
    path = _sprint_east_then_south()
    scent = scent_field()
    tracked = BeliefGrid(BOARD_SIZE)
    old_style = BeliefGrid(BOARD_SIZE, smell_trust=4.0, smell_power=1.0, leak=0.0)
    stale_after = 4

    for step, position in enumerate(path):
        grid = scent.emit(position)
        tracked.diffuse()
        tracked.observe_smell(grid)
        old_style.diffuse()
        old_style.observe_smell(grid)

        if step < stale_after + 1:
            continue  # too early for any cell to count as stale yet
        stale = path[: step - stale_after]

        assert _mass_near(tracked.as_matrix(), position) > _mass_near(
            old_style.as_matrix(), position
        )
        assert _mass_on(tracked.as_matrix(), stale) < _mass_on(old_style.as_matrix(), stale)


def test_the_default_filter_stays_shaped_like_a_blob_not_the_visited_path():
    """The realistic case: once the thief is pinned down and moves off, more
    belief mass sits near its current cell than on the whole stale trail --
    a board-shaped belief, not a comet tail, in absolute terms."""
    path = _linger_then_move()
    scent = scent_field()
    tracked = BeliefGrid(BOARD_SIZE)
    stale_after = 3

    for step, position in enumerate(path):
        grid = scent.emit(position)
        tracked.diffuse()
        tracked.observe_smell(grid)

        if step < stale_after + 1:
            continue
        stale = path[: step - stale_after]
        matrix = tracked.as_matrix()
        assert _mass_near(matrix, position) > _mass_on(matrix, stale)
