"""Subject and body text for the mandatory series-result email (rule 34).

The JSON attachment (`report/result.py::build_result`) IS the binding report;
this text is a human-readable summary riding alongside it, matching the
sibling thief repo's own template (`report/email_summary.py`) and the settled
cross-team convention (copthief-league-protocol SPEC.md 6.1): the body
carries the same result facts as the attachment, not a substitute for it.

`repositories` here is nested by group id (`{group_id: {"cop": url, "thief":
url}}` -- see `report/result_parts.py::repos_of`), unlike the thief repo's
flat `{"cop": url, "thief": url}`, because this artifact lists both peers'
repos rather than only the author's own. `own`'s `group_id` picks this peer's
own entry back out, so the body reads the same either way.
"""

__all__ = ["build_subject", "build_body"]


def build_subject(result_json: dict, own: dict) -> str:
    group_id = own.get("group_id", "unknown-group")
    return f"[UOH26 Final Game] {result_json.get('game_id')} — {group_id} result report"


def build_body(result_json: dict, own: dict) -> str:
    final = result_json.get("final_result", {})
    own_group_id = own.get("group_id", "unknown-group")
    repos = result_json.get("repositories", {}).get(own_group_id, {})
    lines = [
        f"Group: {own_group_id} ({own.get('group_name', 'unnamed')})",
        "",
        f"Game: {result_json.get('game_id')}   uid: {result_json.get('game_uid')}",
        f"Sub-games played: {result_json.get('num_sub_games')}",
        f"Total score: {final.get('total_score', {})}",
        f"Sub-games won: {final.get('sub_games_won', {})}",
        f"Winner: {final.get('winner_group')}",
        f"Tokens: {final.get('tokens_total_series', {})}",
        f"Mutual agreement sha256: {result_json.get('mutual_agreement', {}).get('sha256')}",
        "",
        f"Cop repository:   {repos.get('cop', '')}",
        f"Thief repository: {repos.get('thief', '')}",
        "",
        "The binding report is the attached JSON file (rule 34).",
    ]
    return "\n".join(lines)
