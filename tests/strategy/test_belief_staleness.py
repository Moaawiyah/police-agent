"""Tests for the staleness shrink: unsupported cells fade faster than
reinforced ones, without upsetting the distribution invariant.

Scenarios feed real, per-turn evidence at a fixed cell rather than relying on
packet membership -- ScentField keeps an abandoned cell listed, if faintly,
far longer than any of these sequences run, so "still in the dict" is not a
usable freshness signal on its own (see belief.py's DEFAULT_STALE_SUPPORT).
"""

from police_agent.strategy.belief import BeliefGrid

TARGET = (3, 3)
FAR = (0, 0)


def total(belief: BeliefGrid) -> float:
    return round(sum(sum(row) for row in belief.as_matrix()), 9)


def _run(stale_decay: float, stale_support: float = 0.1, turns: int = 30) -> BeliefGrid:
    """One strong hit at TARGET, then real evidence at FAR every turn after."""
    belief = BeliefGrid(7, stale_decay=stale_decay, stale_support=stale_support)
    belief.observe_smell({f"{TARGET[0]},{TARGET[1]}": 0.9})
    for _ in range(turns):
        belief.diffuse()
        belief.observe_smell({f"{FAR[0]},{FAR[1]}": 0.9})
    return belief


class TestMassConservation:
    def test_it_stays_a_distribution_through_asymmetric_staleness(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.9})
        assert total(belief) == 1.0
        belief.diffuse()
        belief.observe_smell({"5,5": 0.9})
        assert total(belief) == 1.0
        belief.diffuse()
        belief.observe_smell({})
        assert total(belief) == 1.0


class TestReinforcedBeatsAbandoned:
    def test_a_cell_fed_every_turn_beats_one_abandoned_after_the_first(self):
        reinforced = BeliefGrid(7)
        for _ in range(30):
            reinforced.diffuse()
            reinforced.observe_smell({f"{TARGET[0]},{TARGET[1]}": 0.9})
        abandoned = _run(stale_decay=0.85)

        assert reinforced.as_matrix()[TARGET[0]][TARGET[1]] > abandoned.as_matrix()[TARGET[0]][TARGET[1]]

    def test_the_abandoned_cell_ends_up_lower_than_with_staleness_disabled(self):
        disabled = _run(stale_decay=1.0)
        default = _run(stale_decay=0.85)

        assert default.as_matrix()[TARGET[0]][TARGET[1]] < disabled.as_matrix()[TARGET[0]][TARGET[1]]


class TestStrengthensMonotonically:
    def test_a_lower_stale_decay_widens_the_supported_over_abandoned_ratio(self):
        ratios = []
        for decay in (1.0, 0.9, 0.85, 0.8):
            belief = _run(stale_decay=decay)
            m = belief.as_matrix()
            ratios.append(m[FAR[0]][FAR[1]] / m[TARGET[0]][TARGET[1]])

        assert ratios == sorted(ratios)
        assert ratios[-1] > ratios[0]


class TestSupportThreshold:
    def test_a_reading_below_the_bar_still_gets_shrunk(self):
        """Present every turn, but always faint relative to that turn's own
        peak -- proves packet membership alone doesn't count as support."""
        belief = BeliefGrid(7, stale_decay=0.85, stale_support=0.1)
        belief.observe_smell({"3,3": 0.9})
        before = belief.as_matrix()[3][3]
        for _ in range(10):
            belief.diffuse()
            belief.observe_smell({"3,3": 0.05, "0,0": 0.9})  # reading = 0.05/0.9 < 0.1

        assert belief.as_matrix()[3][3] < before


class TestExcludedCellsAreUntouched:
    def test_stale_decay_never_inflates_an_excluded_cells_regrowth(self):
        """0.0 * any stale_decay is still 0.0 on the turn a cell is excluded --
        this mechanism cannot directly push an excluded cell up. The
        pre-existing flat leak still re-seeds a small amount every turn
        regardless (peer/turn_sender.py's known "leak keeps re-seeding every
        cell" wart, unrelated to and not worsened by this change) -- but
        because a walled cell can never appear supported again, every
        following turn's shrink suppresses that regrowth further, so a lower
        stale_decay ends up with LESS residual mass here, never more."""

        def run(decay: float) -> float:
            belief = BeliefGrid(7, stale_decay=decay)
            belief.exclude((3, 3))
            for _ in range(10):
                belief.diffuse()
                belief.observe_smell({"0,0": 0.9})
            return belief.as_matrix()[3][3]

        assert run(0.5) < run(1.0)


class TestDisabled:
    def test_stale_decay_of_one_never_calls_the_shrink(self):
        belief = BeliefGrid(7, stale_decay=1.0)
        belief.observe_smell({"3,3": 0.9})
        before = belief.as_matrix()

        belief._shrink_unsupported(set())  # empty set: would shrink every cell if enabled

        assert belief.as_matrix() == before
