"""The Ollama call, exercised without a model installed or a socket opened.

The request body is asserted because it is the part a passing chat with a
running server would never check: `stream` and `think` off are what keep the
reply a single short line instead of a stream of Qwen's reasoning.
"""

import json
import urllib.error
from contextlib import contextmanager

import pytest

from police_agent.infra.ollama import DEFAULT_MODEL, OllamaError, ask_ollama


@contextmanager
def _response(body: bytes):
    class Fake:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    yield Fake()


def fake_urlopen(monkeypatch, body: bytes = b'{"response": "Times Square is mine."}'):
    """Capture the request that would have gone out, and answer it."""
    sent = {}

    def urlopen(request, timeout=None):
        sent["url"] = request.full_url
        sent["timeout"] = timeout
        sent["payload"] = json.loads(request.data)
        return _response(body).__enter__()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return sent


class TestTheRequest:
    def test_the_models_answer_comes_back_as_plain_text(self, monkeypatch):
        fake_urlopen(monkeypatch)

        assert ask_ollama("taunt him") == "Times Square is mine."

    def test_it_asks_for_one_whole_answer_and_no_thinking(self, monkeypatch):
        """Qwen3 reasons out loud by default, which would fill the token budget."""
        sent = fake_urlopen(monkeypatch)

        ask_ollama("taunt him")

        assert sent["payload"]["stream"] is False
        assert sent["payload"]["think"] is False

    def test_the_shipped_model_is_qwen(self, monkeypatch):
        sent = fake_urlopen(monkeypatch)

        ask_ollama("taunt him")

        assert sent["payload"]["model"] == DEFAULT_MODEL == "qwen3:4b"

    def test_a_system_prompt_rides_in_ollamas_own_field(self, monkeypatch):
        sent = fake_urlopen(monkeypatch)

        ask_ollama("taunt him", system="you are a detective")

        assert sent["payload"]["system"] == "you are a detective"

    def test_no_empty_system_field_is_sent_when_there_is_none(self, monkeypatch):
        sent = fake_urlopen(monkeypatch)

        ask_ollama("taunt him")

        assert "system" not in sent["payload"]

    def test_the_caller_sets_the_deadline_and_the_endpoint(self, monkeypatch):
        sent = fake_urlopen(monkeypatch)

        ask_ollama("taunt him", url="http://elsewhere:1234/api/generate", timeout=2.5)

        assert sent["timeout"] == 2.5
        assert sent["url"] == "http://elsewhere:1234/api/generate"


class TestEveryFailureLooksTheSame:
    @pytest.mark.parametrize(
        "boom",
        [
            urllib.error.URLError("connection refused"),
            TimeoutError("took too long"),
            OSError("socket died"),
        ],
    )
    def test_a_server_that_is_not_there_raises_one_kind_of_error(self, monkeypatch, boom):
        def urlopen(request, timeout=None):
            raise boom

        monkeypatch.setattr("urllib.request.urlopen", urlopen)

        with pytest.raises(OllamaError, match="failed"):
            ask_ollama("taunt him")

    def test_a_reply_that_is_not_json_raises_the_same_error(self, monkeypatch):
        fake_urlopen(monkeypatch, body=b"<html>404</html>")

        with pytest.raises(OllamaError, match="failed"):
            ask_ollama("taunt him")

    def test_a_model_that_is_not_pulled_raises_rather_than_returning_nothing(self, monkeypatch):
        fake_urlopen(monkeypatch, body=b'{"error": "model not found"}')

        with pytest.raises(OllamaError, match="no text"):
            ask_ollama("taunt him", model="qwen3:4b")
