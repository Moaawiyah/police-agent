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
covers only the game_id and, per sub-game, its roles, its outcome, its winning
group and the points each group earned -- plus the totals over them
(`result_parts.agreement_core`). `game_uid` and the sorted group pair are left
out even though both peers derive them identically too: the shape mirrors the
one the grading opponent's independent implementation is expected to hash,
which is the only thing that makes byte-for-byte agreement possible at all.

Everything per-peer is deliberately outside it. Timestamps differ by the clock
skew between two machines. File paths differ by whose disk it is. Token spend
differs because it *is* different, and no peer can measure another's: the
opponent's figure is always reported as 0 rather than estimated, and excluded
from the digest so an honest zero can never cause a disagreement.

Contrast the log artifact, whose `mutual_agreement` is asymmetric on purpose --
see `report/artifacts.py`.
"""

from police_agent.domain.rules import ZEROED_RESULTS
from police_agent.domain.scoring import aggregate
from police_agent.report.ids import SCHEMA_VERSION, consensus_signature, interop_sha256
from police_agent.report.result_parts import (
    agreement_core,
    log_files_of,
    repos_of,
    subgame_block,
    tokens_total_series,
    tokens_used,
)

RESULT_TYPE = "final_game_result"

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


def scoring_from(config=None) -> dict:
    """The signed scoring table, over Appendix Vav's mandatory example values."""
    table = config.get("scoring") if config is not None else None
    return {**DEFAULT_SCORING, **(table if isinstance(table, dict) else {})}


def build_result(
    facts,
    summaries: list,
    scoring: dict | None = None,
    counted_games_played: int = 0,
    counted: bool = False,
) -> dict:
    """The series as one document: every sub-game, the totals, and the digest.

    Takes a *list* of match records because the artifact is match-level while a
    sub-game runs in its own process. One record is a legitimate series of one.

    `counted_games_played` is how many prior *counted* series are on record
    against this opponent; `games_played_including_this` adds the one this
    result is for, but only if `counted` (a `--count` run) -- a warm-up never
    inflates the tally. `counted` is also stored on the artifact itself, since
    it is the only place that ever knows: `report/history.py::archive_completed_series`
    reads it back from here the next time this opponent is played, to keep
    `count_series` accurate without a second source of truth. Per-peer, not
    part of the symmetric digest -- each side's own local history can
    legitimately differ, same reasoning as why token spend sits outside
    `mutual_agreement`.
    """
    table = scoring or DEFAULT_SCORING
    sub_games = [
        {**subgame_block(summary, table), "log_files": log_files_of(summary, facts.game_id)}
        for summary in summaries
    ]
    # A zeroed/sanctioned sub-game's score is withheld from `aggregate` entirely
    # (which already skips an empty row) rather than passed as {a: 0, b: 0} --
    # `aggregate` has no result-type context of its own, so a real 0-0 would
    # otherwise be indistinguishable from a genuine tie and miscounted as one.
    scores = [{} if b["result"] in ZEROED_RESULTS else b["score"] for b in sub_games]
    totals = aggregate(scores, int(table.get("tie_score", 0)))
    core = agreement_core(facts.game_id, sub_games, totals)
    final_result = {**totals, "tokens_total_series": tokens_total_series(sub_games)}
    return {
        "_schema": RESULT_NOTE,
        "schema_version": SCHEMA_VERSION,
        "report_type": RESULT_TYPE,
        "game_id": facts.game_id,
        "game_uid": facts.game_uid,
        "links": facts.links,
        "repositories": repos_of(summaries),
        "timezone": facts.timezone,
        "groups": facts.groups,
        "game_started_at": facts.started_at,
        "game_ended_at": facts.ended_at,
        "num_sub_games": len(sub_games),
        "num_sub_games_agreed": facts.num_sub_games,
        "sub_games": sub_games,
        "final_result": final_result,
        "max_tokens_per_game": facts.token_budget,
        "tokens_used": tokens_used(facts, summaries),
        "counted": counted,
        "games_played_including_this": counted_games_played + (1 if counted else 0),
        "mutual_agreement": {
            "sha256": consensus_signature(core),
            "confirmed": all(block["audit"]["log_verified"] for block in sub_games),
            "scope": "symmetric_outcome",
            "interop_sha256": interop_sha256(core),
            "interop_scope": "symmetric_outcome_ascii",
        },
    }
