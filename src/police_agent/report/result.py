"""The binding artifact: the whole series, scored, and the digest both peers sign.

This is the file rule 32 has each team email to the lecturer separately, and rule
35 attaches the sanction to: if either report is missing, *neither* team scores
for the match, however the board went. It summarises every sub-game -- who played
which side, how it ended, what each group earned -- and totals them for the
league weighting (ch. 9.3.3).

The scoring itself is not computed here. `domain/scoring.py` already turns an
outcome into points from the signed table and sums a series, and it is used live
during a match; a second implementation in the reporting layer would be a second
answer to the same question, which is precisely the disagreement rule 51 is about.

## The mutual-agreement digest is symmetric, and that is the whole point

Both peers must produce the *same* `mutual_agreement.sha256`, because that is how
two independently written reports are shown to describe one match. So the digest
covers only what both sides can derive identically: the identifiers, the sorted
group pair, and per sub-game its number, its outcome, its winning group and the
points each group earned -- plus the totals over them.

Everything per-peer is deliberately outside it. Timestamps differ by the clock
skew between two machines. File paths differ by whose disk it is. Token spend
differs because it *is* different, and no peer can measure another's: the
opponent's figure is always reported as 0 rather than estimated, and excluded
from the digest so an honest zero can never cause a disagreement.

Contrast the log artifact, whose `mutual_agreement` is asymmetric on purpose --
see `report/artifacts.py`.
"""

from police_agent.domain.scoring import aggregate, score_subgame
from police_agent.report.artifacts import roles_of
from police_agent.report.ids import SCHEMA_VERSION, consensus_signature

RESULT_TYPE = "final_result"

# Appendix Vav table 17's own example values, which are also the ones it makes
# mandatory in the absence of a negotiated table. Defaults rather than a crash,
# on the same reasoning as `shared/gatekeeper.py`: a report that refused to be
# produced because one point value was missing would cost both teams the match.
DEFAULT_SCORING = {
    "capture_cop": 20,
    "capture_thief": 5,
    "survival_cop": 5,
    "survival_thief": 10,
    "tie_score": 2,
    "technical_loss": 0,
}

RESULT_NOTE = (
    "The binding end-of-game report (rules 32/35/51), emailed to the lecturer by "
    "each team separately as a JSON attachment. Summarises every sub-game and "
    "totals them for the league weighting. mutual_agreement.sha256 is SYMMETRIC: "
    "both peers must derive the same value, so it covers only the agreed outcome "
    "-- never timestamps, file paths or token spend, which legitimately differ."
)

TOKENS_REMARK = (
    "opponent is always 0: no peer can measure another's model spend, and a "
    "figure we estimated would be one nobody could check. Excluded from "
    "mutual_agreement so an honest zero can never cause a disagreement."
)


def scoring_from(config=None) -> dict:
    """The signed scoring table, over Appendix Vav's mandatory example values."""
    table = config.get("scoring") if config is not None else None
    return {**DEFAULT_SCORING, **(table if isinstance(table, dict) else {})}


def build_result(facts, summaries: list, scoring: dict | None = None) -> dict:
    """The series as one document: every sub-game, the totals, and the digest.

    Takes a *list* of match records because the artifact is match-level while a
    sub-game runs in its own process. One record is a legitimate series of one.
    """
    table = scoring or DEFAULT_SCORING
    sub_games = [subgame_block(summary, table) for summary in summaries]
    totals = aggregate([block["scores"] for block in sub_games], int(table.get("tie_score", 0)))
    core = agreement_core(facts, sub_games, totals)
    return {
        "_schema": RESULT_NOTE,
        "schema_version": SCHEMA_VERSION,
        "artifact_type": RESULT_TYPE,
        "game_id": facts.game_id,
        "game_uid": facts.game_uid,
        "links": facts.links,
        "timezone": facts.timezone,
        "groups": facts.groups,
        "repos": repos_of(summaries),
        "game_started_at": facts.started_at,
        "game_ended_at": facts.ended_at,
        "sub_games_played": len(sub_games),
        "num_sub_games_agreed": facts.num_sub_games,
        "sub_games": sub_games,
        "totals": totals,
        "max_tokens_per_game": facts.token_budget,
        "tokens_used": tokens_used(facts, summaries),
        "mutual_agreement": {
            "confirmed": all(block["audit_passed"] for block in sub_games),
            "sha256": consensus_signature(core),
        },
    }


def subgame_block(summary: dict, scoring: dict) -> dict:
    """One sub-game as the league reads it: sides, outcome, points, evidence."""
    roles = roles_of(summary)
    played = {group: role for role, group in roles.items() if group}
    result = summary.get("result", "")
    return {
        "sub_game_number": int((summary.get("step_zero") or {}).get("sub_game_number", 1)),
        "roles": roles,
        "result": result,
        # A role on the wire, a group in the report: the two peers swap sides
        # across the series, so only the group id means the same thing twice.
        "winner_group": roles.get(str(summary.get("winner") or "")) or None,
        "scores": score_subgame(result, played, scoring),
        "steps": summary.get("steps", 0),
        "audit_passed": bool((summary.get("audit") or {}).get("passed")),
        # Rule 53: each sub-game may run different code, so the commit is per
        # sub-game and per group rather than once for the series.
        "github_commits": commits_of(summary),
    }


def agreement_core(facts, sub_games: list, totals: dict) -> dict:
    """Exactly what both peers derive identically, and nothing else.

    Built as its own object rather than by deleting keys from the artifact, so a
    field added to the report later cannot silently join the digest and start
    disagreeing with an opponent who has not added it too.
    """
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
    """The commit each group declared for this sub-game, keyed by group id."""
    both = (summary.get("identity") or {}, summary.get("peer_identity") or {})
    return {
        side["group_id"]: side.get("github_commit", "") for side in both if side.get("group_id")
    }


def repos_of(summaries: list) -> dict:
    """Both groups' repository links -- four in total, as ch. 9.4 requires.

    Taken from the last sub-game that named them: a group that corrected a link
    mid-series meant the correction, and the grader needs the one that resolves.
    """
    found: dict = {}
    for summary in summaries:
        for side in (summary.get("identity") or {}, summary.get("peer_identity") or {}):
            if side.get("group_id") and side.get("repos"):
                found[side["group_id"]] = side["repos"]
    return found


def tokens_used(facts, summaries: list) -> dict:
    """The series total against the agreed ceiling (Appendix He 54)."""
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
