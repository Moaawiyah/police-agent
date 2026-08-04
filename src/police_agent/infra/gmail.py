"""Mailing the binding result to the lecturer, as an attachment and nothing else.

Rule 32 has each team send the end-of-game report itself, and rule 35 attaches
the sanction: no report, no points -- for *either* team, however the board went.
Rule 34 fixes the form. The report must be structured, machine-readable JSON sent
as an attached file; a plain-text summary in the body is grounds for rejection,
which under rule 35 costs the round. So the body here is four lines of prose that
say where the report is, and carry no game data at all.

Appendix Alef's sample writes the result into the body. Rule 34 forbids it, and
where the appendix's convenience and a numbered rule disagree the rule wins.

## Off by default, and inert when off

`email.enabled` is false in the shipped example and `email.mode` is `"draft"`.
Nothing here opens a socket until somebody sets both deliberately: a draft is
written to a local `.eml` file, which is also the only kind of draft
`gmail.send` permits (see `infra/gmail_client.py`).

## Through the Gatekeeper, with its own daily quota

Rule 28 wants outbound calls rate limited, and ch. 9.3.1's first gate is a daily
quota -- the one that matters here, because Google's limit is per day and per
account, and exceeding it is what gets the account suspended rather than merely
throttled. The mail gate is a separate `Gatekeeper` from the runtime's: figure
13's gates protect a *provider's* allowance, and Ollama's rate window has nothing
to do with Google's. Only a real send passes through it; writing a local draft
calls nobody and spends nothing.
"""

import base64
from email.message import EmailMessage
from pathlib import Path

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail_client import SCOPE, send_raw
from police_agent.shared.gatekeeper import Gatekeeper
from police_agent.shared.quota import DailyQuota

__all__ = ["SCOPE", "build_message", "draft_path", "gmail_reporter", "write_draft"]

DRAFT, SEND = "draft", "send"

DEFAULTS = {
    "enabled": False,
    "recipient": "rmisegal+uoh26finalgame@gmail.com",
    "mode": DRAFT,
    "credentials_file": "credentials.json",
    "token_file": "token.json",
    "daily_limit": 20,
    "quota_file": "logs/.mail_quota.json",
}

# Rule 34: the body is not the report. It says where the report is and stops.
BODY = (
    "Automated end-of-game report from the police agent.\n\n"
    "The binding report is the attached JSON file. This body deliberately "
    "carries no game data: the specification requires a structured, "
    "machine-readable report and rejects free-text ones.\n"
)


def build_message(recipient: str, subject: str, attachment: Path) -> EmailMessage:
    """The report as mail: prose body, JSON attachment, nothing else."""
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(BODY)
    message.add_attachment(
        Path(attachment).read_bytes(),
        maintype="application",
        subtype="json",
        filename=Path(attachment).name,
    )
    return message


def api_body(message: EmailMessage) -> dict:
    """What Gmail's `messages.send` takes: the whole RFC 822 message, base64url."""
    return {"raw": base64.urlsafe_b64encode(bytes(message)).decode()}


def draft_path(attachment: Path) -> Path:
    """`draft_<result filename>.eml`, beside the report it carries."""
    report = Path(attachment)
    return report.with_name(f"draft_{report.stem}.eml")


def write_draft(message: EmailMessage, path: Path) -> Path:
    """The message as a file any mail client can open, sent by a human or not at all."""
    Path(path).write_bytes(bytes(message))
    return Path(path)


def settings(config=None) -> dict:
    """The `[email]` block, over the shipped defaults."""
    read = config.get if config is not None else (lambda _key, default=None: default)
    return {key: _or_default(read(f"email.{key}"), value) for key, value in DEFAULTS.items()}


def gmail_reporter(config=None, gate: Gatekeeper | None = None):
    """A bound `report(path) -> str | None`, which is the shape the SDK holds.

    `None` means reporting is switched off, which is the shipped state and not an
    error: a practice match should not mail the lecturer. Anything else is a
    sentence saying what happened, because the one failure mode rule 35 punishes
    is a report nobody noticed was never sent.
    """
    options = settings(config)
    gate = gate or _mail_gate(options)

    def report(attachment) -> str | None:
        if not options["enabled"]:
            return None
        message = build_message(options["recipient"], _subject(attachment), Path(attachment))
        if options["mode"] == DRAFT:
            return f"draft written to {write_draft(message, draft_path(attachment))}"
        if options["mode"] != SEND:
            raise ConfigError(f"Unknown email.mode {options['mode']!r}: use {DRAFT!r} or {SEND!r}")
        identifier = gate.submit(
            lambda: send_raw(api_body(message), options["credentials_file"], options["token_file"])
        )
        return f"sent to {options['recipient']} as message {identifier}"

    return report


def _mail_gate(options: dict) -> Gatekeeper:
    """The rate limiter and the daily allowance Google's quota actually needs."""
    return Gatekeeper(quota=DailyQuota(options["daily_limit"], options["quota_file"]))


def _subject(attachment) -> str:
    """Names the file, so a mailbox of these can be sorted without opening one."""
    return f"P2P Cop-Chase report: {Path(attachment).stem}"


def _or_default(value, default):
    return default if value is None else value
