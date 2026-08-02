"""The collaborator the turn loop calls but does not own.

The hint writer is injected rather than imported, so the runtime is complete
without it and gains real behaviour later without being edited. What it must
*not* be is silently absent: the turn loop calls it every turn, so a missing
collaborator would be an AttributeError mid-match.

This file used to hold `NullScent` alongside it, emitting nothing because the
scent field had not been built. It has been: see `domain/scent.py`, which the
runtime now constructs from the agreed terms.
"""


def silent_hint(state, capture_claim) -> str:
    """The default hint: nothing.

    The specification allows a free-text cue with every turn, and permits it to
    mislead. Writing one is the optional language layer, which is a separate
    step and must stay out of the move path entirely -- so the shipped default
    says nothing rather than leaking a true position by accident.
    """
    return ""
