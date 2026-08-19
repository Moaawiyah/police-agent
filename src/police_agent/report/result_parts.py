"""Small projections used by the binding series result artifact."""

from police_agent.domain.rules import ZEROED_RESULTS
from police_agent.domain.scoring import aggregate, score_subgame
from police_agent.report.artifacts import roles_of
from police_agent.report.ids import log_filename
from police_agent.report.peer_commits import commits_of

TOKENS_REMARK = (
    "opponent's figure is the peer's own sealed per-step token counts, "
    "revealed and tamper-checked at the audit; 0 if the peer's schema omits "
    "them or the audit did not pass. Excluded from mutual_agreement so an "
    "honest zero can never cause a disagreement."
)


def subgame_block(summary: dict, scoring: dict) -> dict:
    """Project one sub-game into the league result schema.

    Field names and shape mirror the sibling thief repository's own result
    artifact (`report_type`, `score` singular, `tie`, nested `audit`, ...): the
    grading opponent at match time is some other student's independent
    implementation, and this is the convention both sides need to agree on for
    `mutual_agreement.sha256` (see `agreement_core`) to ever land on the same
    value byte-for-byte.
    """
    roles = roles_of(summary)
    result = summary.get("result", "")
    zeroed = result in ZEROED_RESULTS
    # A zeroed/sanctioned outcome (timeout, technical loss, tamper forfeit) is
    # credited to nobody -- winner_group stays null and tie stays false -- even
    # though the runtime's own `summary["winner"]` field may name a role, since
    # that field serves live GUI/audit display, not the binding score.
    winner_role = str(summary.get("winner") or "")
    winner_group = None if zeroed else next((g for g, r in roles.items() if r == winner_role), None)
    own_gid = (summary.get("identity") or {}).get("group_id", "")
    opp_gid = (summary.get("peer_identity") or {}).get("group_id", "")
    passed = bool((summary.get("audit") or {}).get("passed"))
    tokens = summary.get("tokens") or {}
    spent = int(tokens.get("tokens_total") or 0)
    peer_spent = int(tokens.get("peer_tokens_total") or 0)
    return {
        "sub_game_number": int((summary.get("step_zero") or {}).get("sub_game_number", 1)),
        "roles": roles,
        "started_at": summary.get("started_at", ""),
        "ended_at": summary.get("ended_at", ""),
        "result": result,
        "winner_group": winner_group,
        "tie": (not zeroed) and winner_group is None,
        "github_commit": commits_of(summary),
        "tokens": {own_gid: spent, opp_gid: peer_spent},
        "score": score_subgame(result, roles, scoring),
        "audit": {"log_verified": passed, "tampered": not passed},
        "steps": summary.get("steps", 0),
    }


def log_files_of(summary: dict, game_id: str) -> dict:
    """Where each group's own log for this sub-game is filed, relative to `logs/`."""
    number = int((summary.get("step_zero") or {}).get("sub_game_number", 1))
    name = log_filename(game_id, number)
    own_gid = (summary.get("identity") or {}).get("group_id", "")
    opp_gid = (summary.get("peer_identity") or {}).get("group_id", "")
    return {gid: f"{gid}/{name}" for gid in (own_gid, opp_gid) if gid}


def series_totals(summaries: list, scoring: dict) -> dict:
    """Aggregate every sub-game summary into one series-level result.

    Shared by the binding report (`report/result.py`) and the live GUI, so a
    series winner means the same thing wherever it is shown. A zeroed/
    sanctioned sub-game's score is withheld from `aggregate` entirely (which
    already skips an empty row) rather than passed through as `{a: 0, b: 0}`
    -- `aggregate` has no result-type context of its own, so a real 0-0 would
    otherwise be indistinguishable from a genuine tie and miscounted as one.
    """
    blocks = [subgame_block(summary, scoring) for summary in summaries]
    scores = [{} if block["result"] in ZEROED_RESULTS else block["score"] for block in blocks]
    return aggregate(scores, int(scoring.get("tie_score", 0)))


def tokens_total_series(sub_games: list) -> dict:
    """Each group's spend, summed across the whole series (opponent always 0)."""
    totals: dict = {}
    for block in sub_games:
        for group, spent in block.get("tokens", {}).items():
            totals[group] = totals.get(group, 0) + spent
    return totals


def agreement_core(game_id: str, sub_games: list, totals: dict) -> dict:
    """Return only fields both peers can derive identically.

    Deliberately narrower than the full result: no `game_uid` or `groups`, and
    each sub-game keeps only `roles`/`result`/`winner_group`/`score` -- the same
    reduced shape the sibling thief repo hashes (`report/emit.py`'s `symmetric`
    dict), so an independently written opponent that follows the same
    convention reproduces this exact digest.
    """
    return {
        "game_id": game_id,
        "aggregate": totals,
        "sub_games": [
            {
                "sub_game_number": block["sub_game_number"],
                "roles": block["roles"],
                "result": block["result"],
                "winner_group": block["winner_group"],
                "score": block["score"],
            }
            for block in sub_games
        ],
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
    token_blocks = [summary.get("tokens") or {} for summary in summaries]
    spent = sum(int(block.get("tokens_total") or 0) for block in token_blocks)
    peer_spent = sum(int(block.get("peer_tokens_total") or 0) for block in token_blocks)
    return {
        "_remark": TOKENS_REMARK,
        "by_group": {facts.own_group_id: spent, facts.opponent_group_id: peer_spent},
        "total": spent,
        "budget_per_series": facts.token_budget,
        "within_budget": not facts.token_budget or spent <= facts.token_budget,
    }
