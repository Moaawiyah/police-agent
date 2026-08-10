"""Small projections used by the binding series result artifact."""

from police_agent.domain.scoring import aggregate, score_subgame
from police_agent.report.artifacts import roles_of

TOKENS_REMARK = (
    "opponent is always 0: no peer can measure another's model spend, and a "
    "figure we estimated would be one nobody could check. Excluded from "
    "mutual_agreement so an honest zero can never cause a disagreement."
)


def subgame_block(summary: dict, scoring: dict) -> dict:
    """Project one sub-game into the league result schema."""
    roles = roles_of(summary)
    played = {group: role for role, group in roles.items() if group}
    result = summary.get("result", "")
    return {
        "sub_game_number": int((summary.get("step_zero") or {}).get("sub_game_number", 1)),
        "roles": roles,
        "result": result,
        "winner_group": roles.get(str(summary.get("winner") or "")) or None,
        "scores": score_subgame(result, played, scoring),
        "steps": summary.get("steps", 0),
        "audit_passed": bool((summary.get("audit") or {}).get("passed")),
        "github_commits": commits_of(summary),
    }


def series_totals(summaries: list, scoring: dict) -> dict:
    """Aggregate every sub-game summary into one series-level result.

    Shared by the binding report (`report/result.py`) and the live GUI, so a
    series winner means the same thing wherever it is shown.
    """
    scores = [subgame_block(summary, scoring)["scores"] for summary in summaries]
    return aggregate(scores, int(scoring.get("tie_score", 0)))


def agreement_core(facts, sub_games: list, totals: dict) -> dict:
    """Return only fields both peers can derive identically."""
    return {
        "game_id": facts.game_id,
        "game_uid": facts.game_uid,
        "groups": facts.groups,
        "sub_games": [
            {
                "sub_game_number": block["sub_game_number"],
                "result": block["result"],
                "winner_group": block["winner_group"],
                "scores": block["scores"],
            }
            for block in sub_games
        ],
        "totals": totals,
    }


def commits_of(summary: dict) -> dict:
    """Return each declared commit keyed by group id."""
    both = (summary.get("identity") or {}, summary.get("peer_identity") or {})
    return {
        side["group_id"]: side.get("github_commit", "")
        for side in both
        if side.get("group_id")
    }


def repos_of(summaries: list) -> dict:
    """Return the latest repository links declared by either group."""
    found: dict = {}
    for summary in summaries:
        for side in (summary.get("identity") or {}, summary.get("peer_identity") or {}):
            if side.get("group_id") and side.get("repos"):
                found[side["group_id"]] = side["repos"]
    return found


def tokens_used(facts, summaries: list) -> dict:
    """Total this peer's model spend against the agreed series ceiling."""
    spent = sum(
        int((summary.get("tokens") or {}).get("tokens_total") or 0) for summary in summaries
    )
    return {
        "_remark": TOKENS_REMARK,
        "by_group": {facts.own_group_id: spent, facts.opponent_group_id: 0},
        "total": spent,
        "budget_per_series": facts.token_budget,
        "within_budget": not facts.token_budget or spent <= facts.token_budget,
    }
