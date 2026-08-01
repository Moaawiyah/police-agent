"""League scoring: an outcome becomes points, a series of sub-games becomes a result.

Pure functions with no I/O, so the same code serves the live runtime, the result
JSON emitter and the tests. Every point value comes from the agreed, signed
config/*/game.json "scoring" block (specification Appendix Vav, table 17) rather
than being hardcoded here, because the two peers negotiate that table.
"""

from police_agent.constants import Role
from police_agent.domain.rules import CAPTURE, SURVIVAL

# outcome -> (key for whoever played police, key for whoever played thief)
_POINT_KEYS = {
    CAPTURE: ("capture_cop", "capture_thief"),
    SURVIVAL: ("survival_cop", "survival_thief"),
}


def score_subgame(result: str, roles: dict[str, str], scoring: dict) -> dict[str, int]:
    """Points each group earns from one sub-game.

    `roles` maps group id -> the role that group played this sub-game. Any
    outcome that is neither a capture nor a survival is a technical loss and
    scores the same for both sides, so no peer profits from stalling, crashing
    or forfeiting.
    """
    if result not in _POINT_KEYS:
        return dict.fromkeys(roles, scoring.get("technical_loss", 0))
    cop_key, thief_key = _POINT_KEYS[result]
    return {
        group: scoring[cop_key] if role == Role.POLICE else scoring[thief_key]
        for group, role in roles.items()
    }


def aggregate(subgame_scores: list[dict[str, int]], tie_score: int) -> dict:
    """Sum a series of sub-game scores into the final match result.

    Reports the running total per group, how many sub-games each group won, how
    many were drawn, and the overall winner. A two-group series that ends level
    is a tie: there is no winner and the agreed tie bonus goes to both.
    """
    groups = sorted({group for scores in subgame_scores for group in scores})
    total = {group: sum(s.get(group, 0) for s in subgame_scores) for group in groups}

    sub_games_won = dict.fromkeys(groups, 0)
    ties = 0
    for scores in subgame_scores:
        if not scores:
            continue
        best = max(scores.values())
        winners = [group for group, points in scores.items() if points == best]
        if len(winners) == 1:
            sub_games_won[winners[0]] += 1
        else:
            ties += 1

    series_tie = len(groups) == 2 and total[groups[0]] == total[groups[1]]
    if series_tie:
        total = {group: points + tie_score for group, points in total.items()}

    return {
        "total_score": total,
        "sub_games_won": sub_games_won,
        "ties": ties,
        "winner_group": None if series_tie or not total else max(total, key=total.get),
        "series_tie": series_tie,
    }
