"""The step-zero declaration: what machine and what code are about to play.

Two of the specification's binding rules turn out to be one object. Rule 24 asks
for a signed hardware declaration and rule 53 for the commit hash of the code
being played, and ch. 5.5 packs both into a single "step-zero" record made
*before the first move*, together with the code version, the group name and the
sub-game number.

Why one record rather than a field somewhere: ch. 5.5 wants the declaration to
be unforgeable in retrospect. Writing the specs into a report at the end would
not be -- by then the match is over and a peer that lost could describe whatever
hardware flattered it. So the declaration is sealed under the same commit-reveal
this repository already uses for turns, its digest is handed to the opponent
during the handshake (`peer/runtime.py`), and its nonce is not revealed until the
end-of-game audit. Between those two moments the content is fixed and the
opponent holds the proof of it, which is the property the chapter is asking for.

The course reference instead signs the declaration with a bare `sha256(json)`
that anybody can recompute, and therefore anybody can forge. We emit that field
too, for interop with the artifact schema the opposing team parses -- but it is
this sealed record, not that hash, that actually satisfies the rule.

It rides at `records[0]`, ahead of the turns, so the audit re-verifies it exactly
like any other step and a tampered declaration fails the log.
"""

from police_agent.domain.crypto import CommitReveal
from police_agent.infra.gitcommit import commit_hash, working_tree_dirty
from police_agent.infra.hardware import hardware_spec
from police_agent.peer.sealing import now_iso
from police_agent.shared.version import CODE_VERSION, REPOSITORY_URL

# Step 0 by construction: the turns are 1..n, so the declaration sorts ahead of
# them and `audit_records` reports a failure against it as step 0.
STEP_ZERO = 0
RECORD_TYPE = "step_zero"


def step_zero_payload(config) -> dict:
    """Everything ch. 5.5 asks a peer to declare before it moves."""
    return {
        "step": STEP_ZERO,
        "record_type": RECORD_TYPE,
        "declared_at": now_iso(),
        "group_id": config.get("game.group_id", "unknown-group"),
        "group_name": config.get("game.group_name", "unnamed"),
        "members": config.get("game.members", []),
        "repos": config.get("game.repos", {}),
        "sub_game_number": config.get("game.sub_game_number", 1),
        "code_version": CODE_VERSION,
        "repository_url": REPOSITORY_URL,
        # Named, not measured: the model this peer is configured to talk to. The
        # move is always pure Python (Appendix He 25); this is the verbal layer.
        "llm_model": config.get("llm.model", "none"),
        "github_commit": commit_hash(config),
        # Kept beside the hash rather than suffixed onto it, so `github_commit`
        # stays something the grader can actually check out.
        "working_tree_dirty": working_tree_dirty(),
        "hardware_spec": hardware_spec(),
    }


def sealed_step_zero(config) -> dict:
    """The declaration as a sealed record, in the same shape as a sealed turn."""
    payload = step_zero_payload(config)
    return {"payload": payload, **CommitReveal.seal(payload)}


def is_step_zero(record: dict) -> bool:
    """Whether a revealed record is a declaration rather than a turn.

    Reads the payload rather than trusting the position, because this is also
    applied to the *opponent's* revealed log, where we control neither.
    """
    payload = record.get("payload") if isinstance(record, dict) else None
    return isinstance(payload, dict) and payload.get("record_type") == RECORD_TYPE


def turn_records(records: list) -> list:
    """Just the turns, for anything that pairs records with moves.

    The replay player walks records alongside the move log, and those two only
    line up once the declaration is out of the way.
    """
    return [record for record in records or [] if not is_step_zero(record)]


def step_zero_of(records: list) -> dict:
    """The declaration payload from a revealed log, or `{}` if it has none.

    An opponent that predates this feature simply has no declaration, which is
    reported as absent rather than raised on -- a missing declaration is the
    other team's rule-24 problem and no reason to abandon a playable match.
    """
    for record in records or []:
        if is_step_zero(record):
            return record.get("payload", {})
    return {}
