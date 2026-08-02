"""Decision: what a brain hands back to the turn layer.

Kept in its own module so the move policy and the barrier policy can both
produce one without importing each other.

It carries the chosen `Action` and nothing else the game depends on. The
rationale is plain Python text written for the game log and the replay: it makes
a past decision reviewable without re-running the brain. It is never sent to the
opponent, and it never influences the move -- language belongs to the optional
banter layer, which is a separate step and must stay out of the move path.
"""

from dataclasses import dataclass

from police_agent.domain.actions import Action


@dataclass(frozen=True)
class Decision:
    """One turn's chosen action, and why it was chosen. Frozen like the Action."""

    action: Action
    rationale: str
