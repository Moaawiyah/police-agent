"""What the end-of-game JSON says about tokens, the rate limiter and floods.

Appendix He 54 requires the token figure in the summary, and Appendix He 28/29
require the two gates to exist. The tests that matter most here are the ones
about restraint: the inbound detector may observe an opponent as hard as it
likes, but a turn it disliked must still be played, because a peer that dropped
a legal turn to defend itself would forfeit the match it was defending.
"""

from police_agent.peer.runtime import PoliceRuntime
from police_agent.shared.tokens import Usage
from tests.conftest import config_with
from tests.infra.test_ollama import fake_urlopen
from tests.peer.fake_transport import FakeTransport, thief_turn, thief_turns

CAUGHT = {"claim": [1, 0], "caught": True}
COUNTED = b'{"response": "Grand Central is watched.", "prompt_eval_count": 120, "eval_count": 18}'


def runtime(incoming, **overrides) -> PoliceRuntime:
    """A police runtime wired to a scripted thief, not yet run."""
    return PoliceRuntime(config_with(**overrides), FakeTransport(incoming=incoming))


def spending(subject: PoliceRuntime, prompt: int, completion: int) -> None:
    """Charge every turn's hint to the ledger, as a real model call would."""
    original = subject.hint_writer

    def writer(state, capture_claim, opponent_hint=""):
        subject.tokens.record(Usage(prompt, completion))
        return original(state, capture_claim, opponent_hint)

    subject.hint_writer = writer


class TestTheTokenReport:
    def test_a_match_with_no_model_reports_an_honest_zero(self):
        """Template banter costs nothing, and nothing is what it must claim."""
        summary = runtime(thief_turns(3)).run()

        assert summary["tokens"]["tokens_total"] == 0
        assert summary["tokens"]["model_calls"] == 0

    def test_the_summary_carries_this_step_and_this_sub_game(self):
        summary = runtime(thief_turns(3)).run()

        assert "tokens_step" in summary["tokens"]
        assert "tokens_total" in summary["tokens"]

    def test_what_the_turns_spent_is_what_the_sub_game_reports(self):
        subject = runtime(thief_turns(3))
        spending(subject, 100, 20)

        summary = subject.run()

        assert summary["tokens"]["tokens_total"] == 360  # three turns at 120
        assert summary["tokens"]["prompt_tokens"] == 300

    def test_the_step_figure_is_the_last_turns_spend_and_not_the_whole_match(self):
        subject = runtime(thief_turns(3))
        spending(subject, 100, 20)

        summary = subject.run()

        assert summary["tokens"]["tokens_step"] == 120

    def test_the_agreed_series_budget_travels_with_the_figure(self):
        """Appendix Vav table 18: ~200000 for the series, from the signed file."""
        summary = runtime(thief_turns(2)).run()

        assert summary["tokens"]["budget_per_series"] == 200000

    def test_a_series_total_is_not_invented_by_a_peer_that_cannot_see_one(self):
        summary = runtime(thief_turns(2)).run()

        assert "tokens_series" not in summary["tokens"]


class TestTheGatekeeperIsInTheRecord:
    def test_the_summary_shows_the_limits_the_match_was_played_under(self, config):
        summary = runtime(thief_turns(2)).run()

        assert summary["gatekeeper"]["limits"]["requests_per_minute"] == 30
        assert summary["gatekeeper"]["limits"]["queue_depth"] == 100

    def test_a_match_that_called_nothing_out_says_so(self):
        summary = runtime(thief_turns(2)).run()

        assert summary["gatekeeper"]["submitted"] == 0
        assert summary["gatekeeper"]["dos"]["tripped"] is False

    def test_a_real_model_call_is_counted_by_the_runtimes_own_gate(self, monkeypatch):
        """The gate in the summary must be the one the turns actually went through."""
        fake_urlopen(monkeypatch, body=COUNTED)

        summary = runtime(thief_turns(3), trash_talk__provider="ollama").run()

        assert summary["gatekeeper"]["submitted"] == 3
        assert summary["gatekeeper"]["sent"] == 3

    def test_a_real_model_call_lands_in_the_runtimes_own_ledger(self, monkeypatch):
        """One gate and one ledger: the two must be measuring the same calls."""
        fake_urlopen(monkeypatch, body=COUNTED)

        summary = runtime(thief_turns(3), trash_talk__provider="ollama").run()

        assert summary["tokens"]["model_calls"] == 3
        assert summary["tokens"]["tokens_total"] == 414  # three calls at 138


class TestTheInboundFloodDetector:
    def test_every_message_the_opponent_sends_is_counted(self):
        summary = runtime(thief_turns(4)).run()

        assert summary["inbound_dos"]["peak_per_minute"] == 4.0

    def test_a_repeated_turn_counts_as_traffic_even_though_it_is_not_a_turn(self):
        """A peer that only ever repeats itself is exactly what this watches for."""
        summary = runtime([thief_turn(1), thief_turn(1), thief_turn(2)]).run()

        assert summary["inbound_dos"]["peak_per_minute"] == 3.0

    def test_an_ordinary_match_never_looks_like_a_flood(self):
        summary = runtime(thief_turns(5)).run()

        assert summary["inbound_dos"]["tripped"] is False

    def test_the_line_is_set_far_above_anything_a_real_game_could_reach(self):
        subject = runtime([])

        assert subject.inbound_dos.limit_per_minute == 6000.0

    def test_a_tripped_detector_still_lets_every_turn_be_played(self):
        """Defending ourselves by dropping a legal turn would lose the game."""
        subject = runtime([thief_turn(1), thief_turn(2, claim_response=CAUGHT)])
        subject.inbound_dos.record(100_000)

        summary = subject.run()

        assert (summary["result"], summary["winner"]) == ("technical_loss", "police")
        assert summary["inbound_dos"]["tripped"] is True
