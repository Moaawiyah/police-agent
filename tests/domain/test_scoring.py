"""Tests for league scoring and the series tie rule (pure functions)."""

from police_agent.domain.scoring import aggregate, score_subgame

# Mirrors the "scoring" block of config/*/game.json.
SCORING = {
    "capture_cop": 20,
    "capture_thief": 5,
    "survival_cop": 5,
    "survival_thief": 10,
    "tie_score": 2,
    "technical_loss": 0,
}
ROLES = {"g1": "police", "g2": "thief"}


class TestScoreSubgame:
    def test_capture_rewards_the_police_group_most(self):
        assert score_subgame("capture", ROLES, SCORING) == {"g1": 20, "g2": 5}

    def test_survival_rewards_the_thief_group_most(self):
        assert score_subgame("survival", ROLES, SCORING) == {"g1": 5, "g2": 10}

    def test_points_follow_the_role_not_the_group(self):
        swapped = {"g1": "thief", "g2": "police"}
        assert score_subgame("capture", swapped, SCORING) == {"g1": 5, "g2": 20}

    def test_any_other_outcome_is_a_technical_loss_for_both(self):
        assert score_subgame("timeout", ROLES, SCORING) == {"g1": 0, "g2": 0}
        assert score_subgame("technical_loss", ROLES, SCORING) == {"g1": 0, "g2": 0}

    def test_technical_loss_value_comes_from_the_agreed_table(self):
        scoring = {**SCORING, "technical_loss": -1}
        assert score_subgame("timeout", ROLES, scoring) == {"g1": -1, "g2": -1}

    def test_tamper_forfeit_scores_like_a_capture_for_the_winner(self):
        assert score_subgame("tamper_forfeit", ROLES, SCORING, winner="g1") == {
            "g1": 20,
            "g2": 0,
        }

    def test_tamper_forfeit_follows_the_winners_role_not_a_fixed_side(self):
        swapped = {"g1": "thief", "g2": "police"}
        assert score_subgame("tamper_forfeit", swapped, SCORING, winner="g1") == {
            "g1": 5,
            "g2": 0,
        }

    def test_tamper_forfeit_with_no_resolvable_winner_falls_back_to_technical_loss(self):
        assert score_subgame("tamper_forfeit", ROLES, SCORING, winner=None) == {
            "g1": 0,
            "g2": 0,
        }
        assert score_subgame("tamper_forfeit", ROLES, SCORING, winner="ghost") == {
            "g1": 0,
            "g2": 0,
        }


class TestAggregate:
    def test_single_subgame(self):
        result = aggregate([{"g1": 20, "g2": 5}], tie_score=2)
        assert result["total_score"] == {"g1": 20, "g2": 5}
        assert result["sub_games_won"] == {"g1": 1, "g2": 0}
        assert result["winner_group"] == "g1"
        assert result["series_tie"] is False

    def test_series_sums_and_picks_a_winner(self):
        result = aggregate(
            [{"g1": 20, "g2": 5}, {"g1": 5, "g2": 10}, {"g1": 20, "g2": 5}], tie_score=2
        )
        assert result["total_score"] == {"g1": 45, "g2": 20}
        assert result["sub_games_won"] == {"g1": 2, "g2": 1}
        assert result["winner_group"] == "g1"

    def test_level_series_awards_the_tie_bonus_to_both(self):
        result = aggregate([{"g1": 20, "g2": 5}, {"g1": 5, "g2": 20}], tie_score=2)
        assert result["series_tie"] is True
        assert result["winner_group"] is None
        assert result["total_score"] == {"g1": 27, "g2": 27}

    def test_drawn_subgame_counts_as_a_tie_not_a_win(self):
        result = aggregate([{"g1": 0, "g2": 0}, {"g1": 20, "g2": 5}], tie_score=2)
        assert result["ties"] == 1
        assert result["sub_games_won"] == {"g1": 1, "g2": 0}

    def test_empty_series_has_no_winner(self):
        result = aggregate([], tie_score=2)
        assert result["total_score"] == {}
        assert result["winner_group"] is None
        assert result["series_tie"] is False

    def test_empty_subgame_entries_are_skipped(self):
        result = aggregate([{}, {"g1": 20, "g2": 5}], tie_score=2)
        assert result["ties"] == 0
        assert result["winner_group"] == "g1"
