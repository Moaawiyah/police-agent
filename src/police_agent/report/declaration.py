"""The pre-game declaration: everything about the match that does not change.

Ch. 9.3.3 gives this file one job -- pin, before the sub-games are played, the
facts that hold across all of them: who the two groups are, their four
repository links, their MCP addresses, the hardware each is running, the model
each uses and the token ceiling they agreed. Roles alternate across a series, so
no role and no sub-game number appear here.

Both groups are described, which is only possible because the handshake carries
each peer's identity: `groups.group_1` is us and `group_2` the opponent, filled
from what it sent. Anything it did not send is reported as "unknown" rather than
guessed -- an opponent that declares nothing has a rule-24 problem of its own,
and inventing plausible hardware for it would be the one way to make that our
problem too.

The per-group `signature` is the schema's, and it is worth being honest about
what it proves: it is a plain SHA-256 over the block, so anybody can recompute
it and therefore anybody can forge it. It is emitted for interop with the
opposing team's parser. The property ch. 5.5 actually asks for -- a declaration
that cannot be rewritten after the fact -- is carried by `peer/step_zero.py`,
whose sealed record has its digest published at the handshake and its nonce
withheld until the audit.
"""

from police_agent.report.ids import SCHEMA_VERSION, consensus_signature

DECLARATION_TYPE = "pre_game_declaration"
UNKNOWN = "unknown"

SCHEMA_NOTE = (
    "Static declaration for the WHOLE game (the full series of sub-games) "
    "between two teams. The single home for every field that does NOT change "
    "while the sub-games are played: team identity, members, cop/thief "
    "repository URLs, MCP server URLs, hardware spec, LLM model, the agreed "
    "max-tokens-per-game cap, and the game start/end times. Roles switch across "
    "the sub-games, so no role and no sub_game_number appear here. Data that "
    "changes per sub-game lives in the log and result artifacts."
)

# The six fields the artifact publishes, and the internal name each comes from.
# The projection is not cosmetic: the schema says `gpu_model` where we record
# `gpu_type`, and it omits `os` and the GPU core count entirely. Both survive in
# the sealed step-zero payload, which is where ch. 5.5's requirement is met and
# where no foreign parser can object to an extra key.
_DECLARED_HARDWARE = (
    ("cpu_type", "cpu_type"),
    ("cpu_freq_mhz", "cpu_freq_mhz"),
    ("cpu_cores", "cpu_cores"),
    ("ram_gb", "ram_gb"),
    ("gpu_model", "gpu_type"),
    ("vram_gb", "vram_gb"),
)


def build_declaration(facts, summary: dict) -> dict:
    """The declaration artifact, keys in the order the schema lists them."""
    identity = summary.get("identity") or {}
    peer = summary.get("peer_identity") or {}
    return {
        "_schema": SCHEMA_NOTE,
        "schema_version": SCHEMA_VERSION,
        "declaration_type": DECLARATION_TYPE,
        "game_id": facts.game_id,
        "game_uid": facts.game_uid,
        "links": facts.links,
        "timezone": facts.timezone,
        "game_started_at": facts.started_at,
        "game_ended_at": facts.ended_at,
        "num_sub_games": facts.num_sub_games,
        "max_tokens_per_game": facts.token_budget,
        "groups": {"group_1": group_block(identity), "group_2": group_block(peer)},
    }


def group_block(identity: dict) -> dict:
    """One group's static facts, with the schema's signature over them.

    The signature is added last and covers everything above it, so recomputing
    it means dropping the key and hashing the rest -- which is exactly what a
    verifier on the other side does.
    """
    block = {
        "group_id": identity.get("group_id") or UNKNOWN,
        "group_name": identity.get("group_name") or UNKNOWN,
        "members": identity.get("members") or [],
        "repos": identity.get("repos") or {},
        "mcp_servers": identity.get("mcp_servers") or {},
        "llm_model": identity.get("llm_model") or UNKNOWN,
        "hardware_spec": declared_hardware(identity.get("hardware_spec")),
    }
    return {**block, "signature": consensus_signature(block)}


def declared_hardware(spec) -> dict:
    """The six fields the schema publishes, from the eight we record.

    An opponent that sent nothing yields six "unknown"s rather than an empty or
    absent block: the schema's shape is fixed, and a parser on the other side
    should not have to branch on whether we filled it in.
    """
    source = spec if isinstance(spec, dict) else {}
    return {declared: source.get(internal, UNKNOWN) for declared, internal in _DECLARED_HARDWARE}
