"""Asking an OpenAI-compatible chat endpoint for a line of text, and nothing else.

The sibling of `infra/ollama.py`, same shape and same rules: `chat_asker`
returns a bound `ask(prompt, system) -> str`, every call goes through the
Gatekeeper, and the provider's own token counts are reported rather than
estimated. z.ai's `/paas/v4` speaks this protocol, as do most hosted models.

Two things differ from the local server, and both are deliberate:

* the endpoint is METERED, so `shared/tokens.py` accounting stops being a
  formality -- Appendix Vav table 21 budgets a series, and the ledger this
  feeds is what proves the budget held;
* it needs a credential, which is read from the environment and never from
  config. A key committed to `game.toml` would be a key published to the
  opponent's repository the moment the two are compared.
"""

import json
import os
import urllib.error
import urllib.request

from police_agent.exceptions import PoliceAgentError
from police_agent.shared.gatekeeper import Gatekeeper
from police_agent.shared.tokens import Usage

DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_MODEL = "GLM-4.7-FlashX"
API_KEY_ENV = "ZAI_API_KEY"

# A hint is capped at fifteen words by the agreed terms, so there is no reason
# to let the model run on -- and on a metered endpoint every token is charged.
_MAX_TOKENS = 96


class ChatApiError(PoliceAgentError):
    """The hosted model could not be reached, or did not answer usefully."""


def api_key(env: str = API_KEY_ENV) -> str:
    """The credential, from the environment only.

    Absent is a normal state, not a crash: the banter layer falls back to a
    canned line, so a peer with no key still plays a complete match.
    """
    return (os.environ.get(env) or "").strip()


def _endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _messages(prompt: str, system: str) -> list[dict]:
    messages = [{"role": "system", "content": system}] if system else []
    return [*messages, {"role": "user", "content": prompt}]


def ask_chat_usage(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 8.0,
    key: str | None = None,
) -> tuple[str, Usage]:
    """One completion, plus what the provider says it cost.

    Every failure -- no credential, endpoint down, timeout, malformed reply --
    is one `ChatApiError`, because the caller's only decision is whether it got
    a line or has to fall back to a canned one.
    """
    token = api_key() if key is None else key
    if not token:
        raise ChatApiError(f"No API key: export {API_KEY_ENV} before using this provider")
    body = json.dumps(
        {
            "model": model,
            "messages": _messages(prompt, system),
            "max_tokens": _MAX_TOKENS,
            "stream": False,
            # Reasoning off: a fifteen-word taunt needs none, and thinking
            # tokens are billed and counted against the series budget like any
            # other. A provider that does not know the key ignores it.
            "thinking": {"type": "disabled"},
        }
    ).encode()
    request = urllib.request.Request(
        _endpoint(base_url),
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise ChatApiError(f"Chat endpoint {base_url} unreachable: {exc}") from exc
    return _text_of(payload), _usage_of(payload)


def _text_of(payload: dict) -> str:
    """The assistant's line, or an error rather than a silent empty string."""
    choices = payload.get("choices") or []
    if not choices:
        raise ChatApiError(f"Chat endpoint returned no choices: {str(payload)[:200]}")
    content = (choices[0].get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ChatApiError("Chat endpoint returned an empty completion")
    return content.strip()


def _usage_of(payload: dict) -> Usage:
    """What the provider charged, as it reported it -- never estimated."""
    usage = payload.get("usage") or {}
    return Usage(int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))


def chat_asker(
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 8.0,
    gate: Gatekeeper | None = None,
    ledger=None,
    budget: float | None = None,
):
    """A bound `ask(prompt, system) -> str`, the same shape `ollama_asker` returns.

    Interchangeable with the local asker by design: `strategy/talk.py` and
    `strategy/bluff.py` hold a two-argument function and never learn which
    provider is behind it.
    """
    gate = gate or Gatekeeper()
    allowance = timeout if budget is None else budget

    def ask(prompt: str, system: str = "") -> str:
        """One gated completion: admitted through `gate`, usage recorded to `ledger`."""
        reply, usage = gate.submit(
            lambda: ask_chat_usage(
                prompt, system, model=model, base_url=base_url, timeout=timeout
            ),
            budget=allowance,
        )
        if ledger is not None:
            ledger.record(usage)
        return reply

    return ask
