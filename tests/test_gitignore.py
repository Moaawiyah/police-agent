"""The two OAuth secrets must be ignored by the exact names Appendix A uses.

Appendix A step 4 tells the student to download `credentials.json` into the
working directory, and step 5 has Google's own libraries write `token.json`
beside it. Appendix He rules 39 and 40 make committing either one a project
failure, and the damage is not undone by deleting the file later -- a secret
that reached one commit has to be rotated in the console.

The pattern that was here, `*.credentials.json`, silently failed to cover this:
a leading `*` still needs *something* before the literal `.credentials.json`, so
the bare filename the appendix actually produces was never matched. That is the
kind of bug you only find by asking git, which is what this test does.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The names Appendix A produces, verbatim. Both must be refused by git.
SECRET_FILES = ("credentials.json", "token.json")


def _ignored(name: str) -> bool:
    """Ask git itself, rather than re-implementing its glob rules in the test."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", name],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.parametrize("name", SECRET_FILES)
def test_the_oauth_secrets_are_ignored_by_their_real_names(name: str) -> None:
    assert _ignored(name), f"{name} would be committable (Appendix He rules 39/40)"


@pytest.mark.parametrize("name", SECRET_FILES)
def test_the_secrets_are_not_already_tracked(name: str) -> None:
    """An ignore rule does nothing for a file git is already following."""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", name],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert tracked.returncode != 0, f"{name} is tracked; rotate the secret and untrack it"
