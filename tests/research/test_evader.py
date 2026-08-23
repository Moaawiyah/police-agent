"""The synthetic evader stays inside the rules it is supposed to obey."""

import random

import pytest

from police_agent.domain.board import Board
from research.evader import FLEE, RANDOM, SyntheticEvader


def test_rejects_an_unknown_policy():
    with pytest.raises(ValueError, match="policy must be one of"):
        SyntheticEvader((0, 0), Board(7), "teleport", random.Random(0))


def test_random_walk_only_ever_steps_to_a_legal_neighbour_or_stays():
    board = Board(7)
    evader = SyntheticEvader((3, 3), board, RANDOM, random.Random(1))
    previous = evader.position
    for _ in range(50):
        current = evader.step((0, 0), set())
        assert board.in_bounds(current)
        assert board.distance(previous, current) <= 1
        previous = current


def test_flee_maximises_distance_from_the_police():
    board = Board(7)
    evader = SyntheticEvader((3, 3), board, FLEE, random.Random(1))
    # Police at the top-left corner: every step away increases the gap.
    before = board.distance(evader.position, (0, 0))
    after = board.distance(evader.step((0, 0), set()), (0, 0))
    assert after > before


def test_a_fully_walled_evader_stays_put_rather_than_moving_illegally():
    board = Board(7)
    evader = SyntheticEvader((3, 3), board, RANDOM, random.Random(1))
    walls = {(2, 3), (4, 3), (3, 2), (3, 4)}
    assert evader.step((0, 0), walls) == (3, 3)


def test_never_steps_onto_a_barrier():
    board = Board(7)
    evader = SyntheticEvader((3, 3), board, RANDOM, random.Random(7))
    walls = {(2, 3), (4, 3)}
    for _ in range(30):
        assert evader.step((0, 0), walls) not in walls
