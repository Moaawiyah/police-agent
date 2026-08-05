"""Sanitize and cap model-generated verbal hints before they reach the wire."""

import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)
_COORDINATES = re.compile(
    r"\(?\b\d+\s*,\s*\d+\b\)?|\b(?:row|column|col|cell|square|tile|grid)\s*#?\s*\d+",
    re.IGNORECASE,
)


def _clean(reply: str, max_words: int) -> str:
    text = _THINK_BLOCK.sub(" ", str(reply))
    text = _OPEN_THINK.sub(" ", text)
    if _COORDINATES.search(text):
        return ""
    line = next((part.strip() for part in text.splitlines() if part.strip()), "")
    return _cap(line.strip('"\'` ').replace("*", ""), max_words)


def _cap(hint: str, max_words: int) -> str:
    return " ".join(hint.split()[:max_words])
