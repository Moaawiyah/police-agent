"""Which commit of this repository is playing the match.

Appendix He rule 53 lets a team change its code between games and requires only
one thing in return: every game declares the exact commit it ran, so the grader
can check out that revision and reproduce the agent that actually competed. The
identifier travels twice -- sealed inside the step-zero record, and again as
`github_commit` in the emailed result (ch. 5.5, ch. 9).

Everything here is best effort and nothing raises. A match must not be lost
because the code was run from a tarball, or because `git` was missing from the
PATH, so an unanswerable question is reported as the literal `"unknown"` rather
than as a crash or a guess.

The dirty-tree flag is kept *beside* the hash rather than suffixed onto it. A
`-dirty` marker would make the field unresolvable on GitHub for the grader who
has to check it out, so the warning is recorded as its own boolean in the sealed
payload, where it is evidence rather than a parsing hazard.
"""

import subprocess
from functools import lru_cache
from pathlib import Path

UNKNOWN = "unknown"

# Short: this runs before the handshake, and a wedged git must not become the
# reason the opponent's watchdog gives up on us.
_TIMEOUT = 2.0

# src/police_agent/infra/gitcommit.py -> the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def commit_hash(config=None) -> str:
    """The commit being played, or `"unknown"`.

    A configured `game.github_commit` wins over the probe. That is the escape
    hatch for running from a build artefact with no `.git` alongside it: the
    operator can still declare, truthfully, what was built.
    """
    declared = config.get("game.github_commit") if config is not None else None
    if declared:
        return str(declared)
    return _probed_hash()


@lru_cache(maxsize=1)
def _probed_hash() -> str:
    """`git rev-parse HEAD`, cached: it cannot change mid-match."""
    # HEAD rather than a branch name, so a detached checkout still answers.
    return _git("rev-parse", "HEAD") or UNKNOWN


@lru_cache(maxsize=1)
def working_tree_dirty() -> bool:
    """Whether anything is uncommitted, so the declaration can say so.

    A tree with edits means the sha alone does not describe what ran. Reported
    rather than corrected: refusing to play would be worse, and quietly
    pretending the tree was clean would be the dishonest option.
    """
    return bool(_git("status", "--porcelain"))


def _git(*args: str) -> str:
    """One git command against this repository. Any failure is an empty string."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            ["git", "-C", str(_REPO_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,  # rc 128 outside a repository is an answer, not a crash
        )
    except (OSError, subprocess.SubprocessError):
        return ""  # git absent, not executable, or wedged past the timeout
    return done.stdout.strip() if done.returncode == 0 else ""
