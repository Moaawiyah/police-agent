"""Subject/body text for the mandatory series-result email (rule 34)."""

from police_agent.report.email_summary import build_body, build_subject


def _result_json():
    return {
        "game_id": "MOAAMOHA-vs-MOHAMOAA",
        "game_uid": "abc123",
        "num_sub_games": 2,
        "repositories": {
            "MOAAMOHA": {"cop": "https://github.com/example/cop"},
            "MOHAMOAA": {"thief": "https://github.com/example/thief"},
        },
        "final_result": {
            "total_score": {"MOAAMOHA": 20, "MOHAMOAA": 10},
            "sub_games_won": {"MOAAMOHA": 2, "MOHAMOAA": 0},
            "winner_group": "MOAAMOHA",
            "tokens_total_series": {"MOAAMOHA": 42433, "MOHAMOAA": 13652},
        },
        "mutual_agreement": {"sha256": "deadbeef"},
    }


def _own():
    return {"group_id": "MOAAMOHA", "group_name": "Team MOAAMOHA"}


def test_build_subject_matches_the_required_format():
    subject = build_subject(_result_json(), _own())

    assert subject == "[UOH26 Final Game] MOAAMOHA-vs-MOHAMOAA — MOAAMOHA result report"


def test_build_body_includes_every_required_line():
    body = build_body(_result_json(), _own())

    assert "Group: MOAAMOHA (Team MOAAMOHA)" in body
    assert "Game: MOAAMOHA-vs-MOHAMOAA   uid: abc123" in body
    assert "Sub-games played: 2" in body
    assert "Total score: {'MOAAMOHA': 20, 'MOHAMOAA': 10}" in body
    assert "Sub-games won: {'MOAAMOHA': 2, 'MOHAMOAA': 0}" in body
    assert "Winner: MOAAMOHA" in body
    assert "Tokens: {'MOAAMOHA': 42433, 'MOHAMOAA': 13652}" in body
    assert "Mutual agreement sha256: deadbeef" in body
    assert "The binding report is the attached JSON file (rule 34)." in body


def test_build_body_reads_this_peer_s_own_nested_repository_entry():
    """`repositories` is nested by group id (unlike the sibling thief repo's
    flat shape) because this artifact lists both peers' repos, not just the
    author's own -- `own.group_id` has to pick the right sub-dict back out."""
    body = build_body(_result_json(), _own())

    assert "Cop repository:   https://github.com/example/cop" in body
    assert "Thief repository: " in body  # this group never declared a thief repo


def test_build_body_degrades_gracefully_on_missing_fields():
    body = build_body({}, {})

    assert "Group: unknown-group (unnamed)" in body
