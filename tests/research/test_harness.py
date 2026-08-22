"""The headless harness reproduces, and scores the rules it claims to."""

from police_agent.domain.rules import CAPTURE, SURVIVAL, TIMEOUT
from research import MAX_STEPS
from research.evader import FLEE, RANDOM
from research.harness import Episode, play, timeout_or_survival


def test_the_same_seed_reproduces_the_same_episode():
    assert play(11) == play(11)


def test_different_seeds_produce_different_episodes():
    assert len({play(s) for s in range(20)}) > 1


def test_an_episode_never_runs_past_the_agreed_ceiling():
    for seed in range(25):
        assert 1 <= play(seed, policy=FLEE).steps <= MAX_STEPS


def test_a_random_walker_is_always_caught_and_the_result_says_so():
    episode = play(3, policy=RANDOM)
    assert episode.captured
    assert episode.result == CAPTURE
    assert episode.reason in ("claim", "barrier", "confinement")


def test_an_uncaught_episode_runs_to_the_ceiling_and_scores_survival():
    uncaught = [play(s) for s in range(40) if not play(s).captured]
    assert uncaught, "expected at least one escape against a fleeing evader"
    assert all(e.steps == MAX_STEPS and e.result == SURVIVAL for e in uncaught)


def test_tracking_metrics_stay_inside_their_definitions():
    episode = play(5, policy=RANDOM)
    assert 0.0 <= episode.hit_rate <= 1.0
    assert 0.0 <= episode.mean_true_prob <= 1.0
    assert episode.mean_error >= 0.0


def test_a_short_episode_is_scored_a_timeout_not_a_survival():
    short = Episode(SURVIVAL, "survival", 10, 0, 0, 0.0)
    assert timeout_or_survival(short) == TIMEOUT
    assert timeout_or_survival(short, survival_threshold=10) == SURVIVAL


def test_a_capture_is_scored_a_capture_whatever_the_threshold():
    caught = Episode(CAPTURE, "claim", 4, 0, 0, 0.0)
    assert timeout_or_survival(caught) == CAPTURE


def test_metrics_are_zero_on_an_episode_with_no_scored_turns():
    empty = Episode(CAPTURE, "claim", 0, 0, 0, 0.0)
    assert empty.hit_rate == 0.0 and empty.mean_error == 0.0 and empty.mean_true_prob == 0.0
