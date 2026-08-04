"""The handful of values every artifact repeats, derived once.

All four files carry the same identifiers, the same links block and the same
timestamps. Deriving them in each builder would mean four chances to derive them
differently -- and two artifacts disagreeing about their own `game_uid` is
exactly the kind of fault that survives every local test and only shows up when
the lecturer tries to join the files together.

Frozen, so a builder cannot quietly adjust a shared fact for its own output.
"""

from dataclasses import dataclass

from police_agent.report.ids import TIMEZONE, game_id, game_uid, links

UNKNOWN_GROUP = "unknown-group"


@dataclass(frozen=True)
class ReportFacts:
    """What the four artifacts agree about before any of them is built."""

    game_id: str
    game_uid: str
    own_group_id: str
    opponent_group_id: str
    sub_game_number: int
    started_at: str
    ended_at: str
    num_sub_games: int
    token_budget: int
    timezone: str = TIMEZONE

    @property
    def links(self) -> dict:
        return links(self.game_id)

    @property
    def groups(self) -> list[str]:
        """Both group ids, sorted -- the order the result artifact lists them in."""
        return sorted([self.own_group_id, self.opponent_group_id])


def facts_from(summary: dict, config=None) -> ReportFacts:
    """Read the shared facts out of a match record written by `build_summary`.

    Tolerant of a summary from a match that never reached agreement: an opponent
    that never identified itself leaves `peer_identity` empty, and the report
    still has to be produceable -- a match that failed is exactly the one whose
    report the grader needs. The unknown group then sorts into the name like any
    other string, which is ugly but consistent between the two peers.
    """
    identity = summary.get("identity") or {}
    peer = summary.get("peer_identity") or {}
    own = identity.get("group_id") or UNKNOWN_GROUP
    opponent = peer.get("group_id") or UNKNOWN_GROUP
    terms = summary.get("terms") or {}
    read = config.get if config is not None else (lambda _key, default=None: default)
    return ReportFacts(
        game_id=game_id(own, opponent),
        game_uid=game_uid(terms, own, opponent),
        own_group_id=own,
        opponent_group_id=opponent,
        sub_game_number=int((summary.get("step_zero") or {}).get("sub_game_number", 1)),
        started_at=summary.get("started_at", ""),
        ended_at=summary.get("ended_at", ""),
        num_sub_games=int(terms.get("num_games") or read("game.num_games", 1) or 1),
        token_budget=int(
            (summary.get("tokens") or {}).get("budget_per_series")
            or read("game.token_budget_per_series", 0)
            or 0
        ),
    )
