"""Names and digests both peers must derive identically, without talking.

The `game_id` and `game_uid` are computed, not negotiated: each side sorts the
two group ids and hashes the agreed terms, so two peers reach the same answer
with no extra round trip and no chance of disagreeing about what to call the
match. Sorting is what makes it symmetric -- whoever computes it, the pair
`(a, b)` and `(b, a)` produce the same name.

## The two canonical forms, and why they are not interchangeable

This module deliberately holds *two* JSON canonicalisations that differ only in
whitespace, because the artifact schema uses both and mixing them up produces a
hash that is wrong in a way nothing detects:

* `consensus_signature` -- **default separators** (`", "` / `": "`). Used for
  the declaration's per-group `signature` and for `mutual_agreement.sha256` in
  the log and the result.
* `canonical_sha256` -- **compact** separators, via `crypto.canonical_json`.
  Used for `config_sha256`, and by every commit-reveal commitment in the game.

Both are SHA-256 over sorted keys, so a swapped pair still yields a plausible
64-character digest and every local test of our own artifacts still passes. The
only symptom is that the *opposing team's* recomputation disagrees with ours --
at which point the match's mutual agreement fails and the report is rejected.
Neither form is better; they are simply what the schema the other side parses
already specifies, so both are pinned by tests rather than tidied into one.
"""

import hashlib
import json
import uuid

from police_agent.domain.crypto import canonical_json

# The artifact schema's own version, which is not this project's version and not
# the config file's. It describes the shape of these four files and is fixed by
# the specification, so it is a literal rather than anything of ours.
SCHEMA_VERSION = "1.1"

# Timestamps are emitted as UTC with an explicit offset, so this label is
# descriptive rather than a formatting instruction: it is what the schema
# carries, and reformatting our timestamps to match it would break the ones
# already sealed inside the records.
TIMEZONE = "Asia/Jerusalem"

LINKS_REMARK = (
    "These are logical roles, NOT fixed filenames. Each actual file name is "
    "derived from the game_id so that files from different games are never "
    "mixed. Match-level files (declaration, result) are named "
    "<role>_<game_id>.json; per-sub-game files (config, log) are named "
    "<role>_<game_id>_g<NN>.json where <NN> is the sub_game_number."
)


def game_id(group_a: str, group_b: str) -> str:
    """The match's name: both group ids, sorted, so either peer derives the same."""
    first, second = sorted([str(group_a), str(group_b)])
    return f"{first}-vs-{second}"


def game_uid(terms: dict, group_a: str, group_b: str) -> str:
    """A UUID over the agreed terms and the sorted pair.

    Deterministic on both sides, which is the point: it ties the four files to
    *this* agreement, so a rematch under different terms cannot be filed as the
    same game even though the two group ids have not changed.
    """
    pair = sorted([str(group_a), str(group_b)])
    seed = f"{canonical_json(terms)}|{'|'.join(pair)}"
    return str(uuid.UUID(bytes=hashlib.sha256(seed.encode()).digest()[:16]))


def consensus_signature(data: dict) -> str:
    """SHA-256 over the **spacious** canonical form. See the module docstring.

    Used where the opposing team recomputes the same digest: the declaration's
    group blocks, and `mutual_agreement` in the log and result.
    """
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def canonical_sha256(data: dict) -> str:
    """SHA-256 over the **compact** canonical form. See the module docstring.

    The same bytes every commitment in the game is taken over, reused here for
    `config_sha256` so the agreed terms are pinned the way the schema expects.
    """
    return hashlib.sha256(canonical_json(data).encode()).hexdigest()


def interop_sha256(data: dict) -> str:
    """SHA-256 over the compact, ASCII-only canonical form.

    A second signature alongside `consensus_signature`, over the same result
    digest: escaping every non-ASCII codepoint sidesteps the one place two
    differently implemented peers' "sorted, canonical" JSON can still disagree
    (unicode handling), so an independently written opponent can still
    reproduce at least one of the two.
    """
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def sub_game_tag(number: int) -> str:
    """`g01`, `g02`: the zero-padded suffix per-sub-game filenames carry."""
    return f"g{int(number):02d}"


def log_filename(game_id: str, number: int) -> str:
    """`log_<game_id>_g<NN>.json` -- where `writer.py` files a sub-game's log."""
    return f"log_{game_id}_{sub_game_tag(number)}.json"


def links(identifier: str) -> dict:
    """The cross-reference block every artifact carries.

    The per-sub-game entries keep the literal `g<NN>` rather than resolving to a
    number: the block describes the whole family of files, not the one it sits
    in, so a reader holding any single artifact can find the others.
    """
    return {
        "_remark": LINKS_REMARK,
        "declaration": f"declaration_{identifier}.json",
        "config": f"config_{identifier}_g<NN>.json",
        "log": f"log_{identifier}_g<NN>.json",
        "result": f"result_{identifier}.json",
    }
