"""The symmetric mutual-agreement digest: the actual weight-bearing part of the
report artifact (rule 35 -- a mismatch here costs both teams the match).

Split from test_result.py to keep both files under the project's 150-line
rule; fixtures are defined there and imported here.
"""

from police_agent.report.facts import facts_from
from police_agent.report.result import build_result
from tests.report.test_result import (
    POLICE,
    THIEF,
    _capture,
    _mirrored,
    _result,
    _series,
    _survival,
    digest,
)


class TestTheSymmetricAgreementDigest:
    def test_the_opponents_report_of_the_same_match_lands_on_the_same_digest(self):
        """How two independently written files are shown to describe one match."""
        ours = _result()

        theirs = build_result(facts_from(_mirrored()[0]), _mirrored())

        assert theirs["mutual_agreement"]["sha256"] == ours["mutual_agreement"]["sha256"]

    def test_another_clock_and_another_disk_do_not_move_it(self):
        """Timestamps differ by skew between two machines; paths by whose disk it is."""
        shifted = [
            {**summary, "started_at": "1999-01-01T00:00:00+00:00", "duration_seconds": 999}
            for summary in _series()
        ]

        assert digest(shifted) == digest(_series())

    def test_a_different_token_spend_does_not_move_it(self):
        """It is genuinely different on the two sides, and cannot be measured."""
        spent = [{**summary, "tokens": {"tokens_total": 99999}} for summary in _series()]

        assert digest(spent) == digest(_series())

    def test_disagreeing_about_a_score_moves_it(self):
        flattering = [{**_capture(), "result": "survival"}, _survival()]

        assert digest(flattering) != digest(_series())

    def test_disagreeing_about_a_winner_moves_it(self):
        flattering = [{**_capture(), "winner": "thief"}, _survival()]

        assert digest(flattering) != digest(_series())

    def test_a_shorter_series_moves_it(self):
        assert digest([_capture()]) != digest(_series())

    def test_it_confirms_only_when_every_sub_game_passed_its_audit(self):
        forged = [{**_capture(), "audit": {"passed": False}}, _survival()]

        assert build_result(facts_from(forged[0]), forged)["mutual_agreement"]["confirmed"] is False
        assert _result()["mutual_agreement"]["confirmed"] is True


class TestTokenAccounting:
    def test_it_totals_this_peers_spend_across_the_series(self):
        assert _result()["tokens_used"]["total"] == 300

    def test_the_opponents_spend_is_reported_as_zero_and_never_estimated(self):
        """No peer can measure another's, and a figure nobody could check is worse
        than an honest zero -- which is why it is outside the digest."""
        used = _result()["tokens_used"]

        assert used["by_group"] == {POLICE: 300, THIEF: 0}
        assert "0" in used["_remark"]

    def test_it_says_whether_the_agreed_ceiling_was_respected(self):
        assert _result()["tokens_used"]["within_budget"] is True
        assert _result()["tokens_used"]["budget_per_series"] == 200000

    def test_a_series_with_no_agreed_ceiling_is_never_reported_as_over_it(self):
        summary = {**_capture(), "tokens": {"tokens_total": 5}}

        used = build_result(facts_from(summary), [summary])["tokens_used"]

        assert (used["budget_per_series"], used["within_budget"]) == (0, True)
