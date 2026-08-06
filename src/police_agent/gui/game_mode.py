"""What the window should say about the verbal layer: its mode, and its model.

The specification's Table 22 asks each peer to declare how it produces its
banter, and the distinction it draws is the one that matters here: the *move* is
always pure Python (Appendix He 25, ch. 6.5), and a language model shapes text
and nothing else. A window that showed a model name next to the board could be
read as claiming the model was playing, so the mode is named alongside it.

Pure and Tk-free, so it can be tested headless -- and so the replay player can
reuse it on a recorded log, where the only evidence left is a string.
"""

TEMPLATE_MODE = "Python (template)"
OLLAMA_MODE = "Ollama (local)"
REMOTE_MODE = "Remote LLM"

NO_MODEL = "None"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"

# Recorded model strings that mean "no model was involved".
_NO_MODEL_STRINGS = frozenset({"", "-", "none", "template", "stub"})


def mode_and_model(config) -> tuple[str, str]:
    """The (mode, model) pair for a live peer, read from its private config.

    `trash_talk` is private tuning and never an agreed term, so this reads only
    this peer's own file and claims nothing about the opponent. The model label
    is the literal "None" under the template mode rather than an empty string,
    so the window never leaves a blank where a model name would go.
    """
    if config is None:
        return TEMPLATE_MODE, NO_MODEL
    # Matches strategy/talk.py's own default: an unset key means ollama, not
    # template -- the label must report what the hint writer actually does.
    provider = str(config.get("trash_talk.provider", "ollama") or "ollama").lower()
    model = str(config.get("trash_talk.model", "") or "")
    if provider == "ollama":
        return OLLAMA_MODE, model or DEFAULT_OLLAMA_MODEL
    if provider == "template":
        return TEMPLATE_MODE, NO_MODEL
    # Any other provider is something this peer was configured with but this
    # module has not been taught to name. Reporting it as a remote model is the
    # cautious reading: it says a model is involved without inventing which.
    return REMOTE_MODE, model or str(config.get("llm.model", "") or provider)


def mode_from_recorded_model(model: str) -> tuple[str, str]:
    """The same pair for a replayed log, where only the recorded string survives.

    A log written by a run with no model is reported as template mode rather
    than as an unnamed one: claiming an LLM shaped a match that it did not would
    misreport the run in exactly the direction that flatters it.
    """
    text = str(model or "").strip()
    if text.lower() in _NO_MODEL_STRINGS:
        return TEMPLATE_MODE, NO_MODEL
    return REMOTE_MODE, text
