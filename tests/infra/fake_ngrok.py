"""A stand-in for ngrok: PATH, one child process, and the 4040 agent API.

Split out of `test_tunnel.py` so every ngrok test file can share the one
fake, following the same pattern as `fake_commands.py` and `fake_google.py`.
"""

import io
import json
import subprocess
from pathlib import Path

DOMAIN = "cops.ngrok-free.app"
PUBLIC = f"https://{DOMAIN}"
UNAUTHENTICATED = "ERR_NGROK_4018 authentication failed: this account is not verified"
TAKEN = "ERR_NGROK_334 the domain is already bound to another endpoint"


def published(port: int, *urls: str) -> list[dict]:
    # The shape ngrok's API answers in: it echoes our port back as `localhost`.
    return [{"public_url": url, "config": {"addr": f"http://localhost:{port}"}} for url in urls]


class FakeProcess:
    def __init__(self, deaf: bool = False) -> None:
        self.exit_code: int | None = None
        self.terminated = False
        self.killed = False
        self._deaf = deaf  # ignores terminate, as a wedged agent would

    def poll(self) -> int | None:
        return self.exit_code

    def terminate(self) -> None:
        self.terminated = True
        if not self._deaf:
            self.exit_code = -15

    def wait(self, timeout=None) -> int | None:
        if self._deaf:
            raise subprocess.TimeoutExpired("ngrok", timeout)
        return self.exit_code

    def kill(self) -> None:
        self.killed = True


class FakeNgrok:
    """ngrok as this module can see it: PATH, one child process, the 4040 API."""

    def __init__(self, monkeypatch, tunnels=(), *, already_up=False, dies_saying=None) -> None:
        self.tunnels = list(tunnels)
        self.dies_saying = dies_saying
        self.publish_after = 0  # API polls before the tunnel appears
        self.reported = self.tunnels if already_up else []
        self.commands: list[list[str]] = []
        self.processes: list[FakeProcess] = []
        self._polls = 0
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ngrok")
        monkeypatch.setattr("subprocess.Popen", self._start)
        monkeypatch.setattr("urllib.request.urlopen", self._api)
        monkeypatch.setattr("time.sleep", lambda seconds: None)

    def _start(self, command, **_) -> FakeProcess:
        self.commands.append(command)
        process = FakeProcess()
        if self.dies_saying is not None:
            self.log_of(command).write_text(self.dies_saying, encoding="utf-8")
            process.exit_code = 1
        self.processes.append(process)
        return process

    def _api(self, url, timeout=None) -> io.BytesIO:
        self._polls += 1
        if self.commands and self._polls > self.publish_after:
            self.reported = self.tunnels
        return io.BytesIO(json.dumps({"tunnels": self.reported}).encode())

    @staticmethod
    def log_of(command: list[str]) -> Path:
        return Path(next(arg for arg in command if arg.startswith("--log=")).split("=", 1)[1])
