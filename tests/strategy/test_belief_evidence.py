"""has_scent(): whether a real reading, not just diffusion, has ever landed.

Split out of test_belief.py to stay under the file-length cap. This is what
strategy/barrier.py checks before spending a barrier on an opening belief
that has never actually smelled anything.
"""

from police_agent.strategy.belief import BeliefGrid


class TestHasScent:
    def test_false_until_a_real_reading_arrives(self):
        belief = BeliefGrid(7)
        assert belief.has_scent() is False

        belief.diffuse()  # diffusion alone is not evidence
        assert belief.has_scent() is False

        belief.observe_smell({"2,3": 0.9})
        assert belief.has_scent() is True

    def test_stays_false_after_only_junk_or_silence(self):
        belief = BeliefGrid(7)
        belief.observe_smell({"not-a-cell": 0.9})
        belief.observe_smell({})

        assert belief.has_scent() is False
