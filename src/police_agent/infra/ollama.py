"""Asking a local Ollama server for a line of text, and nothing else.

Kept in `infra/` with the other networking because it is networking: the verbal
layer that decides *what to ask* is `strategy/talk.py`, and it holds a function
of this shape rather than importing a server. That seam is what lets the whole
banter path be tested with no model installed and no socket opened.

Ollama runs on localhost and costs no tokens (Appendix Vav, table 21), so unlike
a hosted model there is no budget to ration -- only latency. The consumption is
reported anyway, because Appendix He 54 requires the figure and because the day
this points at a metered provider the accounting must already be real rather
than something to be added under pressure.

`ollama_asker` is the supported way in, and it goes through the Gatekeeper. This
module's raw call is the primitive the gate runs, not a second door: reaching a
model without passing the rate limiter is the one thing ch. 11 scores against.
"""

import json
import urllib.error
import urllib.request

from police_agent.exceptions import PoliceAgentError
from police_agent.shared.gatekeeper import Gatekeeper
from police_agent.shared.tokens import Usage

DEFAULT_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3:4b"

# A hint is capped at fifteen words by the agreed terms, so there is no reason to
# let the model run on; a short ceiling is also the cheapest way to keep the call
# inside its timeout on a machine with no GPU.
_MAX_TOKENS = 96


class OllamaError(PoliceAgentError):
    """The local model could not be reached, or did not answer usefully."""


def ask_ollama(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_URL,
    timeout: float = 5.0,
) -> str:
    """One completion from a local model, as plain text."""
    return ask_ollama_usage(prompt, system, model, url, timeout)[0]


def ask_ollama_usage(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_URL,
    timeout: float = 5.0,
) -> tuple[str, Usage]:
    """One completion, plus what the server says it cost.

    Every failure -- server down, model not pulled, timeout, malformed reply --
    is raised as `OllamaError` so the caller has exactly one thing to catch. The
    banter is decoration, and the one outcome that must never happen is a game
    lost because a chat model was unavailable.
    """
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Qwen3 reasons out loud unless told not to. The thinking is of no use
        # here and would eat the whole token ceiling before the taunt appeared;
        # `strategy/talk.py` also strips any that arrives, for older servers
        # that do not know this flag.
        "think": False,
        "options": {"num_predict": _MAX_TOKENS},
    }
    if system:
        payload["system"] = system

    request = urllib.request.Request(  # noqa: S310 - fixed local Ollama endpoint
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise OllamaError(f"Ollama call to {model} failed: {exc}") from exc

    reply = body.get("response")
    if not isinstance(reply, str):
        raise OllamaError(f"Ollama returned no text for {model}: {body!r}")
    return reply, _usage(body)


def _usage(body: dict) -> Usage:
    """The server's own counts. Absent fields mean zero, never a guess.

    These are the only two numbers in the reply that describe consumption, and a
    report that estimated from string lengths instead would be a number nobody
    could check -- see `shared/tokens.py`.
    """
    return Usage(int(body.get("prompt_eval_count") or 0), int(body.get("eval_count") or 0))


def ollama_asker(
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_URL,
    timeout: float = 5.0,
    gate: Gatekeeper | None = None,
    ledger=None,
    budget: float | None = None,
):
    """A bound `ask(prompt, system) -> str`, which is the shape callers hold.

    Both halves of the verbal layer want a local model on the same terms, and
    neither should have to know a URL to get one: `strategy/talk.py` writes with
    it, `strategy/bluff.py` reads with it, and a test hands over its own
    two-argument function instead. That shape is deliberately unchanged by the
    accounting -- the ledger is a side channel the caller supplies, so a plain
    two-argument stand-in remains a valid asker and simply consumes nothing.

    `budget` bounds the *whole* interaction, queueing and retries included, and
    defaults to the socket timeout. A taunt shares its turn with the opponent's
    watchdog, so the gate is told to give up rather than to keep trying; raise
    `trash_talk.budget_seconds` to buy retries, at that risk.
    """
    gate = gate or Gatekeeper()
    allowance = timeout if budget is None else budget

    def ask(prompt: str, system: str = "") -> str:
        reply, usage = gate.submit(
            lambda: ask_ollama_usage(prompt, system, model=model, url=url, timeout=timeout),
            budget=allowance,
        )
        if ledger is not None:
            ledger.record(usage)
        return reply

    return ask
