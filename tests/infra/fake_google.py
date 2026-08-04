"""A stand-in for Google's client libraries, installed into `sys.modules`.

The real ones are an optional extra (`police-agent[gmail]`) and are imported
inside the functions that need them, so the seam is the import itself: a test
puts fake modules under the names those imports use and the lazy import picks
them up. That is the same trick `tests/infra/test_tunnel.py` plays on the ngrok
binary, applied to a library instead of a process.

Nothing here reaches the network, and the fake records what it was asked to do
so a test can assert on the *shape* of the call -- which scope was requested,
which body was sent -- rather than on a reply nobody can check.
"""

import sys
from types import ModuleType, SimpleNamespace

MODULES = (
    "googleapiclient",
    "googleapiclient.discovery",
    "google",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.credentials",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
)


class FakeGmail:
    """The whole Google client stack, as much of it as `infra/gmail_client.py` uses."""

    def __init__(self, monkeypatch, token: str = '{"token": "stored"}', valid: bool = True) -> None:
        self.sent: list[dict] = []
        self.scopes: list[list[str]] = []
        self.consented = 0
        self.refreshed = 0
        self._token = token
        self._valid = valid
        for name in MODULES:
            monkeypatch.setitem(sys.modules, name, ModuleType(name))
        sys.modules["googleapiclient.discovery"].build = self._build
        sys.modules["google.auth.transport.requests"].Request = lambda: "request"
        sys.modules["google.oauth2.credentials"].Credentials = self._credentials_class()
        sys.modules["google_auth_oauthlib.flow"].InstalledAppFlow = self._flow_class()

    def _build(self, service, version, credentials=None):
        self.built = (service, version, credentials)
        return SimpleNamespace(users=lambda: SimpleNamespace(messages=lambda: self))

    def send(self, userId=None, body=None):  # noqa: N803 - Google's own parameter name
        self.sent.append({"userId": userId, "body": body})
        return SimpleNamespace(execute=lambda: {"id": "msg-1"})

    def _credentials_class(fake):  # noqa: N805 - a factory, not a method on an instance
        class Credentials:
            valid, expired, refresh_token = fake._valid, not fake._valid, "refresh-me"

            @classmethod
            def from_authorized_user_file(cls, path, scopes):
                fake.scopes.append(list(scopes))
                return cls()

            def refresh(self, request):
                fake.refreshed += 1
                self.valid = True

            def to_json(self):
                return fake._token

        return Credentials

    def _flow_class(fake):  # noqa: N805 - a factory, not a method on an instance
        class InstalledAppFlow:
            @classmethod
            def from_client_secrets_file(cls, path, scopes):
                fake.scopes.append(list(scopes))
                fake.secrets_file = path
                return cls()

            def run_local_server(self, port=0):
                fake.consented += 1
                return fake._credentials_class()()

        return InstalledAppFlow
