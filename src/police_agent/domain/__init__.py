"""The authoritative game: board, rules, moves, scoring and audit.

Everything here is deterministic Python with no network, no Tk and no language
model in it. That is a rule, not an accident -- the specification makes the
engine the arbiter of what legally happened, so a move that depended on a
reachable peer or on an LLM's reply could not be re-derived later from a log.

The audit half (`crypto.py`, `semantic_*.py`) exists for the same reason from
the other direction: at the end of a game every claim the opponent made is
re-checked here against the record, rather than trusted because it arrived
signed.
"""
