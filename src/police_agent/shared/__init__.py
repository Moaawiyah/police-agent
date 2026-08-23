"""Cross-cutting machinery every other layer leans on, owned by none of them.

The gatekeeper and its parts (`admission.py`, `rate_limit.py`, `quota.py`,
`tokens.py`) are the reason this package exists: the rate limits are an agreed
term of the match, so exactly one implementation of them has to serve the peer
link, the language model and the mail reporter alike. Three copies would be
three chances to disagree with the opponent about what the limit was.

`config.py`, `schema.py` and `version.py` are here on the same argument -- what
a config file means, and which layouts this build can read, cannot be a per-
package opinion.
"""
