"""Reading a compass claim out of the thief's free text, and nothing more.

The hint is natural language and may be a lie (ch. 4.4). Before it can be
weighed against anything it has to become a proposition, and this module makes
it the smallest one that is still checkable against the board: a direction, or
nothing. Whether to believe it is `strategy/bluff.py`; how it moves the belief
is `strategy/belief.py`.

A small local model does the reading, because "slipping past the uptown lights"
is a northward claim and no keyword table will ever catch every phrasing of
that. Keywords are the fallback rather than the mechanism, and they are also
what makes this work with no model installed at all.
"""

import re

from police_agent.constants import Direction

# Explicit words only. A landmark is not a direction -- the board is abstract and
# nothing here knows where Harlem is, so guessing from place names would invent
# evidence rather than read it.
_KEYWORDS: tuple[tuple[Direction, tuple[str, ...]], ...] = (
    (Direction.N, ("north", "northern", "northward", "uptown", "upwards?")),
    (Direction.S, ("south", "southern", "southward", "downtown", "downwards?")),
    (Direction.E, ("east", "eastern", "eastward", "rightwards?")),
    (Direction.W, ("west", "western", "westward", "leftwards?")),
)

_ANSWERS = {"N": Direction.N, "S": Direction.S, "E": Direction.E, "W": Direction.W}

_SYSTEM = (
    "You read one line written by a fleeing thief and decide which compass "
    "direction it claims the thief is heading or standing. The line may be a "
    "lie; you are not judging truth, only what is being claimed. Answer with "
    "exactly one character: N, S, E, W, or - if no direction is claimed. "
    "Output that character and nothing else."
)


def claimed_direction(hint: str, ask=None) -> Direction | None:
    """The direction this hint claims, or None if it claims none.

    The model is asked first and keywords catch what it misses or refuses; a
    model that is down, slow or babbling simply leaves the keyword answer
    standing, which is the same outcome as having no model configured.
    """
    text = (hint or "").strip()
    if not text:
        return None
    if ask is not None:
        try:
            spoken = _from_answer(ask(f'The thief said: "{text}"', _SYSTEM))
        except Exception:  # noqa: BLE001 - a silent model is a missing opinion,
            spoken = None  # never a lost game; see the module docstring
        if spoken is not None:
            return spoken
    return _from_keywords(text)


def _from_answer(reply: str) -> Direction | None:
    """The letter the model answered with, ignoring any padding around it.

    A standalone letter, not any letter: small models pad a one-character answer
    however plainly they are told not to, and scanning "The answer is: N" for
    characters finds the E in "The" first.
    """
    text = str(reply)
    letter = re.search(r"\b([NSEW])\b", text, re.IGNORECASE)
    if letter:
        return _ANSWERS[letter.group(1).upper()]
    return _from_keywords(text)  # a model that spelled the word out anyway


def _from_keywords(hint: str) -> Direction | None:
    """A direction named outright, or None when none or several are.

    Several is not a majority vote: "north of the bridge, west of the park"
    claims no single thing, and picking one would be this module inventing a
    claim the thief never made.
    """
    found = {
        direction
        for direction, words in _KEYWORDS
        if any(re.search(rf"\b{word}\b", hint, re.IGNORECASE) for word in words)
    }
    return found.pop() if len(found) == 1 else None
