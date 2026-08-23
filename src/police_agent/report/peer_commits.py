"""Which commit each group played, for the result artifact (rule 53).

Three sources, in falling order of authority:

1. the opponent's handshake identity (`github_commit`);
2. the sealed step-zero record it reveals at the audit, which is tamper-checked
   before we ever read it;
3. a commit the opposing team gave us OUT OF BAND, pinned below.

The third is a last resort and is deliberately visible rather than clever: it
records a value we were told rather than one we were sent, so it must never
override either wire source, and it belongs to a named opponent and role rather
than being applied to whoever happens to be missing a commit. A team that
publishes its commit properly never reaches it.

Roles alternate across a series, so the pin is keyed by the role the opponent
played in THAT sub-game: this peer reports its own Police sub-games (their
Thief) and, as series owner, the imported Thief ones (their Cop) too.
"""

from police_agent.peer.step_zero import step_zero_of
from police_agent.report.artifacts import roles_of

# Given in writing by the opposing team when their agent did not transmit them.
# cosmos77, 2026-08-20: "our commits for the counted game", cop + thief repos.
PINNED_COMMITS = {
    "cosmos77": {
        "police": "8e2db959bbe5a711c3977938d4f2a9baf1aa06d5",
        "thief": "741a56f1e36094bf3b1fc302aa947b2e8247e60f",
    }
}


def pinned_commit(group_id: str, role: str) -> str:
    """The out-of-band commit for `group_id` in `role`, or "" if none is pinned."""
    return (PINNED_COMMITS.get(group_id) or {}).get(role, "")


def commits_of(summary: dict) -> dict:
    """Return each declared commit keyed by group id.

    Ours comes from our own identity and is always present. Theirs falls
    through the three sources above, so a peer that declares its commit on the
    wire is reported from the wire even when a pin exists for it.
    """
    mine = summary.get("identity") or {}
    peer = summary.get("peer_identity") or {}
    commits = {}
    if mine.get("group_id"):
        commits[mine["group_id"]] = mine.get("github_commit", "")
    peer_gid = peer.get("group_id")
    if peer_gid:
        declared = step_zero_of(summary.get("opponent_records") or [])
        commits[peer_gid] = (
            peer.get("github_commit")
            or declared.get("github_commit")
            or pinned_commit(peer_gid, roles_of(summary).get(peer_gid, ""))
        )
    return commits


__all__ = ["PINNED_COMMITS", "commits_of", "pinned_commit"]
