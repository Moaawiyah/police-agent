"""Mailing the binding result to the lecturer: JSON attachment plus a matching
human-readable summary in the body.

Rule 32 has each team send the end-of-game report itself, and rule 35 attaches
the sanction: no report, no points -- for *either* team, however the board went.
Rule 34 fixes the form: the report must be structured, machine-readable JSON,
sent as an attached file. The body (`report/email_summary.py`, shared with the
sibling thief repo's own template) is not a substitute for that file -- it is a
summary alongside it, matching the settled cross-team convention that the body
carries the same result facts the attachment does.

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
import json
from email.message import EmailMessage
from pathlib import Path

from police_agent.exceptions import ConfigError
from police_agent.infra.gmail_client import SCOPE, send_raw
from police_agent.infra.gmail_counted import recipients_for
from police_agent.report.email_summary import build_body, build_subject
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


def build_message(
    recipient: str, subject: str, attachment: Path, body: str = "", cc: list[str] | None = None
) -> EmailMessage:
    """The report as mail: a summary body, and the JSON itself as an attachment."""
    message = EmailMessage()
    message["To"] = recipient
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body or "Attached is this peer's independently generated match report.")
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


def gmail_reporter(config=None, gate: Gatekeeper | None = None, counted: bool = False):
    """A bound `report(path) -> str | None`, which is the shape the SDK holds.

    `None` means reporting is switched off, which is the shipped state and not an
    error: a practice match should not mail the lecturer. Anything else is a
    sentence saying what happened, because the one failure mode rule 35 punishes
    is a report nobody noticed was never sent.

    `counted` is the `--count` CLI flag: see `gmail_counted.recipients_for`.
    """
    options = settings(config)
    gate = gate or _mail_gate(options)

    def report(attachment) -> str | None:
        """Mail (or draft) `attachment`'s report, per this peer's `[email]` config."""
        if not options["enabled"]:
            return None
        # `config` is never None here: `enabled` only turns True through a real
        # config, since `settings(None)` always resolves it to the DEFAULTS false.
        to, cc = recipients_for(options["recipient"], DEFAULTS["recipient"], counted)
        result_json = json.loads(Path(attachment).read_text(encoding="utf-8"))
        own = {
            "group_id": config.get("game.group_id", "unknown-group"),
            "group_name": config.get("game.group_name", "unnamed"),
        }
        subject = build_subject(result_json, own)
        body = build_body(result_json, own)
        message = build_message(to, subject, Path(attachment), body, cc=cc)
        if options["mode"] == DRAFT:
            return f"draft written to {write_draft(message, draft_path(attachment))}"
        if options["mode"] != SEND:
            raise ConfigError(f"Unknown email.mode {options['mode']!r}: use {DRAFT!r} or {SEND!r}")
        identifier = gate.submit(
            lambda: send_raw(api_body(message), options["credentials_file"], options["token_file"])
        )
        note = f"sent to {to}"
        if cc:
            note += f", cc {', '.join(cc)}"
        return f"{note} as message {identifier}"

    return report


def _mail_gate(options: dict) -> Gatekeeper:
    """The rate limiter and the daily allowance Google's quota actually needs."""
    return Gatekeeper(quota=DailyQuota(options["daily_limit"], options["quota_file"]))


def _or_default(value, default):
    return default if value is None else value
