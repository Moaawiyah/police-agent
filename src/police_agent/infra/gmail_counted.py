"""Recipient resolution for a counted (`--count`) send, split out of
`gmail.py` to keep it within the line budget.

`copthief-league-protocol` docs/WARNINGS.md §3, "Make the lecturer's address
unreachable, not merely unconfigured": a generic enabled/disabled boolean only
says sending may happen, so the recipient itself must be the switch. An
uncounted (practice) run must refuse to reach the lecturer even if
`email.recipient` happens to resolve to it -- matched case- and
whitespace-insensitively, per the same section.
"""

from police_agent.exceptions import ConfigError

__all__ = ["recipients_for"]


def recipients_for(configured: str, lecturer: str, counted: bool) -> tuple[str, list[str] | None]:
    """The (to, cc) pair for one send.

    Uncounted: mail goes to `configured` (normally the team's own address for
    practice) -- refused outright if that happens to be the lecturer's, since
    an uncounted run owes nobody a report and must not accidentally spend the
    one meeting that counts (App. E rule 52). Counted: mail goes to the
    lecturer, cc'ing `configured` too so the team keeps its own copy, unless
    `configured` already *is* the lecturer's address.
    """
    if not counted:
        if _matches(configured, lecturer):
            raise ConfigError(
                "email.recipient resolves to the lecturer's address on an uncounted run; "
                "pass --count for a real counted send, or point email.recipient at yourselves"
            )
        return configured, None
    if _matches(configured, lecturer):
        return lecturer, None
    return lecturer, [configured]


def _matches(address: str, lecturer: str) -> bool:
    return address.strip().casefold() == lecturer.strip().casefold()
