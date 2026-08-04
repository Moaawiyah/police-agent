"""The Google half of the reporting chain: one scope, one call, no more.

Split from `infra/gmail.py` for the same reason `ngrok_agent.py` is split from
`tunnel.py`: everything that talks to somebody else's SDK lives on one side of a
seam, and the policy that decides *whether* to talk lives on the other. It is
also what lets the default, offline path be tested with no Google libraries
installed at all.

## The scope is `gmail.send`, and it stays that way

Appendix He rule 30 and Appendix Alef step Gimel both fix it. `gmail.send` can do
exactly one thing -- hand a finished message to Google -- and in particular
cannot read, list or delete anything in the mailbox it is authorised against.
That is the whole point of asking for it: an autonomous agent holding a token for
an account the student also uses for real mail should not be able to read it.

The visible consequence is that this client cannot create a Gmail *draft*.
`users.drafts.create` needs `gmail.compose`, which is a broader grant, so
`mode = "draft"` writes a local `.eml` file instead (`infra/gmail.py`). Rule 30
wins over the convenience.

## The libraries are an optional extra

`pip install police-agent[gmail]`. They are imported inside the functions that
need them, so a default run -- reporting disabled, or writing a local draft --
needs none of them installed and touches no network. An absent library is
reported as a ConfigError naming the extra, because it is a setup problem with a
one-line fix and not a bug to be read as a traceback.
"""

from pathlib import Path

from police_agent.exceptions import ConfigError

# Appendix He rule 30. Never widen this: `gmail.compose` or `gmail.modify` would
# let a stray call touch mail this agent has no business touching.
SCOPE = "https://www.googleapis.com/auth/gmail.send"

_MISSING = (
    "The Gmail reporting libraries are not installed. They are an optional extra "
    "so that a default, offline run needs neither them nor a Google account:\n"
    "  uv pip install 'police-agent[gmail]'\n"
    'Or leave email.mode = "draft" in config/police/game.toml, which writes the '
    "report as a local .eml file and calls nothing."
)


def send_raw(body: dict, credentials_file, token_file) -> str:
    """Hand one already-encoded message to Gmail; return the id it was filed as."""
    service = _service(credentials_file, token_file)
    sent = service.users().messages().send(userId="me", body=body).execute()
    return str(sent.get("id", ""))


def _service(credentials_file, token_file):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ConfigError(_MISSING) from exc
    return build("gmail", "v1", credentials=credentials(credentials_file, token_file))


def credentials(credentials_file, token_file):
    """The stored token, refreshed or freshly consented to (Appendix Alef step Dalet).

    The consent flow is interactive and runs once. It is deliberately not
    attempted silently in the middle of a league match: a run that needs it is a
    run a human is watching, which is why `email.enabled` defaults to false and
    why the first send is something you do on purpose.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise ConfigError(_MISSING) from exc

    token = Path(token_file)
    stored = Credentials.from_authorized_user_file(str(token), [SCOPE]) if token.is_file() else None
    if stored and stored.valid:
        return stored
    if stored and stored.expired and stored.refresh_token:
        stored.refresh(Request())
    else:
        stored = _consent(InstalledAppFlow, credentials_file)
    token.write_text(stored.to_json(), encoding="utf-8")
    return stored


def _consent(flow_class, credentials_file):
    """The one-time browser handshake, over the client secrets you downloaded."""
    secrets = Path(credentials_file)
    if not secrets.is_file():
        raise ConfigError(
            f"Gmail client secrets not found: {secrets}. Download them from the "
            "Google Cloud console (Appendix Alef step Dalet) and save them there; "
            "the file is gitignored by name and must never be committed."
        )
    return flow_class.from_client_secrets_file(str(secrets), [SCOPE]).run_local_server(port=0)
