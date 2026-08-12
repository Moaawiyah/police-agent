"""The verbal layer: what the police says to the thief while it chases.

The specification allows a free-text cue with every turn and permits it to
mislead (ch. 4.4). This module writes ours with a small local model, which
Appendix He 25 bounds: a language model may shape *text and behavioural profile*
and nothing else. It is called from `peer/turn_sender.py` only after the move is
decided, applied and sealed, so nothing here can reach a decision -- ch. 6.5 is
blunt about why, and spatial reasoning stays in Python.

Appendix He 27 forbids direct numeric locations on the wire. The strongest
guarantee against leaking one is not to filter the answer but to never ask the
question: the prompt is told the city, whether the police is closing in, and
what the thief last said -- never a cell, never a distance, never the board.
Coordinates are refused in the reply anyway, since a model told nothing can
still invent something.
"""

import random

from police_agent.infra.ollama import DEFAULT_MODEL, DEFAULT_URL, ollama_asker
from police_agent.shared.gatekeeper import Gatekeeper, GateLimits
from police_agent.strategy.talk_text import _cap, _clean

# The fallback, and only the fallback: Ollama is the mechanism. A model that is
# missing, down or slow costs the banter and nothing else. These name no place.
_FALLBACK_LINES = (
    "Every street you take, I am already waiting at the end of it.",
    "You can keep running. This city gets smaller every hour.",
    "I have your scent now, and this town has nowhere left to hide.",
    "Sooner or later you turn a corner and I am there.",
)


class HintWriter:
    """Writes one taunt per turn, with a local model when there is one."""

    def __init__(
        self,
        ask=None,
        setting: str = "",
        max_words: int = 15,
        every_n_steps: int = 1,
        rng: random.Random | None = None,
    ) -> None:
        """Hold the model hook (or None for fallback-only) and this peer's banter tuning."""
        self._ask = ask  # ask(prompt, system) -> str; None means fallback only
        self._setting = setting or "an unnamed city"
        self._max_words = max(1, int(max_words))
        self._every_n_steps = max(1, int(every_n_steps or 1))
        self._rng = rng or random.Random()
        self._turn = 0

    def __call__(self, state, capture_claim, opponent_hint: str = "") -> str:
        """The line to send with this turn. Never raises, whatever the model does."""
        self._turn += 1
        if self._ask is None or self._turn % self._every_n_steps != 0:
            return self._fallback()
        try:
            reply = self._ask(self._user(capture_claim, opponent_hint), self._system())
        except Exception:  # noqa: BLE001 - see the module docstring: banter never
            return self._fallback()  # costs a game, so every failure is the same
        return _clean(reply, self._max_words) or self._fallback()

    def _fallback(self) -> str:
        return _cap(self._rng.choice(_FALLBACK_LINES), self._max_words)

    def _system(self) -> str:
        """What the model is, and the two limits it must respect."""
        return (
            f"You are a police detective chasing a thief through {self._setting}. "
            f"Reply with ONE taunting line of at most {self._max_words} words. "
            f"Name a real {self._setting} landmark. You may bluff about where you "
            "are. Never write grid coordinates, row or column numbers. "
            "Output the line only: no quotes, no preamble, no explanation."
        )

    def _user(self, capture_claim, opponent_hint: str) -> str:
        """The turn's context -- a mood and a remark, never a location.

        `capture_claim` is set only when the police just stepped onto a cell it
        is claiming, so it stands in for pressure without disclosing where.
        """
        mood = "You are closing in fast." if capture_claim else "You are still searching."
        said = opponent_hint.strip()
        heard = f'The thief just said: "{said}". Answer it.' if said else "The thief said nothing."
        return f"{mood} {heard}"


def resolve_hint_writer(
    config=None, rng: random.Random | None = None, gate=None, ledger=None
) -> HintWriter:
    """Build the hint writer from this peer's private `[trash_talk]` block.

    Every key here is private tuning. The one agreed value it reads is
    `play.hint_max_words`, which is signed: both peers hold the same cap, so a
    longer line breaks the terms rather than merely looking greedy.

    `gate` and `ledger` are passed down by the runtime so that writing a taunt
    and reading one share a single rate limiter and a single token tally. Left
    out, this builds its own of each, which is right for a standalone caller and
    wrong for a match -- two gates would let through twice the agreed rate.
    """
    get = config.get if config is not None else (lambda _key, default=None: default)
    # `or` rather than a bare default throughout: a key present but empty or null
    # means "I did not choose", and should land on the shipped value.
    provider = str(get("trash_talk.provider") or "ollama").lower()
    max_words = get("play.hint_max_words") or 15
    setting = get("play.setting") or ""
    every = get("trash_talk.every_n_steps") or 1

    if provider != "ollama":
        # `template` keeps the canned lines; anything unrecognised lands here too,
        # because a typo in a private config should cost banter, not the match.
        return HintWriter(None, setting, max_words, every, rng)

    return HintWriter(asker_from_config(get, gate, ledger), setting, max_words, every, rng)


def asker_from_config(get, gate=None, ledger=None):
    """The local model this peer talks to, from its private `[trash_talk]` block.

    Shared with `strategy/bluff.py`: writing a taunt and reading one are the same
    model on the same server, and configuring them apart would only get them out
    of step. The gate is built from the *agreed* limits when none is handed down,
    so even an asker made in isolation is behind the rate limiter.
    """
    timeout = float(get("trash_talk.timeout_seconds") or 5.0)
    return ollama_asker(
        model=get("trash_talk.model") or DEFAULT_MODEL,
        url=get("trash_talk.ollama_url") or DEFAULT_URL,
        timeout=timeout,
        gate=gate or Gatekeeper(GateLimits.from_getter(get)),
        ledger=ledger,
        budget=float(get("trash_talk.budget_seconds") or timeout),
    )
