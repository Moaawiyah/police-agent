"""The model asker `talk.py` and `bluff.py` both call, and nothing else.

Split out of `talk.py` to keep it under the project's 150-line cap: which
provider answers a prompt is plumbing, not part of what a hint says or
whether it was sealed as honest.
"""

from police_agent.infra.ollama import DEFAULT_MODEL, DEFAULT_URL, ollama_asker
from police_agent.infra.openai_compat import DEFAULT_BASE_URL, chat_asker
from police_agent.infra.openai_compat import DEFAULT_MODEL as DEFAULT_CHAT_MODEL
from police_agent.shared.gatekeeper import Gatekeeper, GateLimits

# Providers that actually reach a model. Anything else -- `template`, or a typo
# in a private config -- keeps the canned lines rather than costing the match.
GLM = "glm"
OLLAMA = "ollama"
MODEL_PROVIDERS = frozenset({OLLAMA, GLM})

# The shipped default. A peer that sets nothing gets the hosted model, so the
# banter does not depend on a local server being installed and running; without
# ZAI_API_KEY it fails on the first call and lands on the canned lines, exactly
# as an absent Ollama does. `trash_talk.provider = "ollama"` restores the local
# path, and `"template"` reaches no model at all.
DEFAULT_PROVIDER = GLM


def asker_from_config(get, gate=None, ledger=None):
    """The model this peer talks to, from its private `[trash_talk]` block.

    Shared with `strategy/bluff.py`: writing a taunt and reading one are the same
    model on the same budget, and configuring them apart would only get them out
    of step. The gate is built from the *agreed* limits when none is handed down,
    so even an asker made in isolation is behind the rate limiter.

    Both providers return the same bound `ask(prompt, system)`, so nothing above
    this line knows whether the model is local or hosted -- only the default
    timeout differs, since a network round trip is not a loopback one.
    """
    provider = str(get("trash_talk.provider") or DEFAULT_PROVIDER).lower()
    gate = gate or Gatekeeper(GateLimits.from_getter(get))
    if provider == GLM:
        timeout = float(get("trash_talk.timeout_seconds") or 8.0)
        return chat_asker(
            model=get("trash_talk.model") or DEFAULT_CHAT_MODEL,
            base_url=get("trash_talk.api_url") or DEFAULT_BASE_URL,
            timeout=timeout,
            gate=gate,
            ledger=ledger,
            budget=float(get("trash_talk.budget_seconds") or timeout),
        )
    timeout = float(get("trash_talk.timeout_seconds") or 5.0)
    return ollama_asker(
        model=get("trash_talk.model") or DEFAULT_MODEL,
        url=get("trash_talk.ollama_url") or DEFAULT_URL,
        timeout=timeout,
        gate=gate,
        ledger=ledger,
        budget=float(get("trash_talk.budget_seconds") or timeout),
    )
