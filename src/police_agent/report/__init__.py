"""The four JSON artifacts the specification's reporting chain is built from.

Ch. 9.3.3 defines a declaration, a config, a log and a result -- one set per
match, sharing a `game_uid`, each filename derived from the `game_id`, so files
from different games can never be mixed up. The result is the binding one, sent
to the lecturer by both peers separately (rules 32/35/51).

Pure serialisation over plain dicts: no sockets, no Tk, no game state. Every
builder takes what `peer/summary.py` already recorded and returns a dict. That
is what lets the whole reporting chain be tested without playing a match, and
what keeps the schema -- which is an agreement with another team's parser --
separate from the rules, which are ours.
"""
