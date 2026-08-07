"""The token total shown once, at game over -- not a live-ticking counter."""

from tests.gui.test_live_apply import SUMMARY, VIEW, apply


def test_game_over_reports_the_token_total_once_not_live():
    tokens = {"tokens_total": 142, "prompt_tokens": 98, "completion_tokens": 44, "model_calls": 3}
    summary = {**SUMMARY, "tokens": tokens}

    window = apply({"type": "game_over", "summary": summary, "view": VIEW})

    assert window.labels["tokens"] == "142 across 3 calls (98 prompt / 44 completion)"


def test_a_match_with_no_model_calls_says_so_rather_than_showing_a_bare_zero():
    window = apply({"type": "game_over", "summary": SUMMARY, "view": VIEW})

    assert window.labels["tokens"] == "0 (no model calls)"
