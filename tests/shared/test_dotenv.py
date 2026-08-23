"""Loading a gitignored `.env` into the environment.

A convenience, so every failure mode has to be survivable: a missing file, a
malformed line, and a variable the caller already set all leave the process
running with whatever it had.
"""

import os

from police_agent.shared.dotenv import load_dotenv

NAME = "POLICE_AGENT_DOTENV_TEST"


def write(tmp_path, text: str):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


class TestLoading:
    def test_a_plain_pair_reaches_the_environment(self, tmp_path, monkeypatch):
        monkeypatch.delenv(NAME, raising=False)
        load_dotenv(write(tmp_path, f"{NAME}=secret-value\n"))

        assert os.environ[NAME] == "secret-value"

    def test_quotes_and_whitespace_are_stripped(self, tmp_path, monkeypatch):
        monkeypatch.delenv(NAME, raising=False)
        load_dotenv(write(tmp_path, f"  {NAME} = 'secret-value'  \n"))

        assert os.environ[NAME] == "secret-value"

    def test_a_value_containing_equals_survives_intact(self, tmp_path, monkeypatch):
        """API keys and base64 secrets routinely contain '='."""
        monkeypatch.delenv(NAME, raising=False)
        load_dotenv(write(tmp_path, f"{NAME}=a=b=c\n"))

        assert os.environ[NAME] == "a=b=c"


class TestWhatItRefusesToDo:
    def test_an_existing_variable_is_never_overwritten(self, tmp_path, monkeypatch):
        """An explicit `KEY=... uv run ...` must beat the file, not lose to it."""
        monkeypatch.setenv(NAME, "from-the-shell")
        load_dotenv(write(tmp_path, f"{NAME}=from-the-file\n"))

        assert os.environ[NAME] == "from-the-shell"

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert load_dotenv(tmp_path / "nothing-here") == {}

    def test_comments_and_blanks_and_junk_are_skipped(self, tmp_path, monkeypatch):
        monkeypatch.delenv(NAME, raising=False)
        loaded = load_dotenv(write(tmp_path, f"# a comment\n\nno-equals-sign\n{NAME}=kept\n"))

        assert list(loaded) == [NAME]

    def test_it_reports_names_and_never_values(self, tmp_path, monkeypatch):
        """A caller that logs the result must not be able to leak a key."""
        monkeypatch.delenv(NAME, raising=False)
        loaded = load_dotenv(write(tmp_path, f"{NAME}=secret-value\n"))

        assert "secret-value" not in str(loaded)
