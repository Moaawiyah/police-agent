"""The two collaborators the turn loop calls but does not own.

Both belong to later build steps, and both are injected rather than imported, so
the runtime is complete now and gains their real behaviour later without being
edited. What they must *not* be is silently absent: the turn loop calls them
every turn, so a missing collaborator would be an AttributeError mid-match.

`NullScent` is the one to watch. It emits nothing, which is honest -- this peer
has no scent field yet -- but it means an opponent receives no signal from us and
must fall back on its prior. A match played this way runs correctly end to end
and is still worth running to prove the wiring, but it is not a fair test of
either strategy. Build step 6 replaces it with a real decaying field.
"""

from police_agent.constants import Cell


class NullScent:
    """Emits no trail. Placeholder until the scent field of build step 6."""

    def emit(self, position: Cell) -> dict:
        """The grid this peer would broadcast. Empty: there is no field yet."""
        return {}


def silent_hint(state, capture_claim: Cell | None) -> str:
    """The default hint: nothing.

    The specification allows a free-text cue with every turn, and permits it to
    mislead. Writing one is the optional language layer, which is a separate
    step and must stay out of the move path entirely -- so the shipped default
    says nothing rather than leaking a true position by accident.
    """
    return ""
