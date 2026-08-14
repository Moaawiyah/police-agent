"""`observe_smell`: folding one scent reading into the posterior.

Split out of test_belief.py to keep both files inside the 150-line rule. The
property worth defending here is that a reading is trusted by its own peak,
not by an absolute scale, and that nothing it does not mention is erased.
"""

from police_agent.strategy.belief import BeliefGrid


def total(belief: BeliefGrid) -> float:
    """Rounded past float noise: the invariant is "sums to one"."""
    return round(sum(sum(row) for row in belief.as_matrix()), 9)


class TestObserving:
    def test_the_strongest_reading_becomes_the_belief(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.2, "6,6": 0.9, "3,3": 0.5})

        assert belief.most_likely() == (6, 6)

    def test_silence_is_not_evidence_of_absence(self):
        """An empty grid must not wipe out what the last one established."""
        belief = BeliefGrid(7)
        belief.observe_smell({"1,1": 0.7})
        belief.observe_smell({})

        assert belief.most_likely() == (1, 1)

    def test_older_evidence_is_not_erased_by_a_new_reading(self):
        """This is the whole difference from the argmax placeholder it replaced:
        a second, unrelated reading must not reset the distribution -- the first
        cell's mass should still beat an untouched cell's, even once it is no
        longer the most likely."""
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.9})
        belief.observe_smell({"5,5": 0.9})

        matrix = belief.as_matrix()
        assert matrix[0][0] > matrix[3][3]  # (3, 3) was never observed at all

    def test_a_fresh_reading_is_trusted_by_its_own_peak_not_absolute_scale(self):
        """`reading = scent / peak` is normalised WITHIN each packet, so a
        reading's strongest cell is always fully trusted however faint it is in
        absolute terms -- a decaying trail's last surviving cell reads the same
        as a reading straight off a fresh emission. That is the deliberate
        trade for tracking a moving thief: the newest evidence is never starved
        just because the whole field has faded."""
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.9})  # a strong, fresh reading
        belief.observe_smell({"5,5": 0.1})  # faint in absolute terms, but its own peak

        assert belief.most_likely() == (5, 5)

    def test_relative_weighting_within_one_reading_is_unaffected(self):
        """Normalisation is per-packet, not per-cell -- two cells in the SAME
        reading still rank by their relative intensity."""
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.9, "6,6": 0.3})

        matrix = belief.as_matrix()
        assert matrix[0][0] > matrix[6][6]

    def test_an_empty_grid_is_safe_and_leaves_belief_unobserved(self):
        belief = BeliefGrid(7)
        belief.observe_smell({})

        assert total(belief) == 1.0
        assert belief.has_scent() is False

    def test_an_all_zero_grid_is_safe_and_boosts_nothing(self):
        """A zero peak means there is nothing to normalise against -- not a
        division by zero, and not evidence either."""
        belief = BeliefGrid(7)
        belief.observe_smell({"0,0": 0.0, "1,1": 0.0})

        assert total(belief) == 1.0
        matrix = belief.as_matrix()
        assert len({round(p, 12) for row in matrix for p in row}) == 1  # still flat
        assert belief.has_scent() is False

    def test_a_trail_is_still_remembered_a_turn_after_it_went_quiet(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"6,6": 0.9})

        belief.diffuse()
        belief.observe_smell({})

        row, col = belief.most_likely()
        assert abs(row - 6) + abs(col - 6) <= 1  # still on the thief, not back at the centre

    def test_junk_from_another_teams_implementation_is_skipped_not_fatal(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"not-a-cell": 0.9, "9,9": 0.9, "1,1": "loud", "2,4": 0.6})

        assert belief.most_likely() == (2, 4)
        assert total(belief) == 1.0

    def test_a_negative_reading_with_a_fractional_power_does_not_go_complex(self):
        """Untrusted wire data, clamped before `**smell_power` (belief.py's own note)."""
        belief = BeliefGrid(2, smell_power=1.5)
        belief.observe_smell({"0,0": -0.9})

        assert isinstance(belief.as_matrix()[0][0], float)
        assert total(belief) == 1.0

    def test_excluding_a_cell_rules_it_out_entirely(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"2,2": 0.9})
        belief.exclude((2, 2))

        assert belief.as_matrix()[2][2] == 0.0
        assert belief.most_likely() != (2, 2)

    def test_excluding_a_cell_off_the_board_is_ignored_not_fatal(self):
        belief = BeliefGrid(7)
        belief.exclude((9, 9))

        assert total(belief) == 1.0
