"""A stand-in for every binary the hardware and git probes shell out to.

Modelled on `tests/infra/test_tunnel.py`'s FakeNgrok: the constructor takes over
`subprocess.run` and the platform lookups, so a test states what the machine
answers and never depends on what the machine actually is. Without it these
tests would pass on the developer's Mac and fail in CI, which is the opposite of
what a test about "what machine am I on" should do.
"""

import subprocess
from types import SimpleNamespace

MISSING = FileNotFoundError("no such binary")
TIMEOUT = subprocess.TimeoutExpired(cmd="probe", timeout=2.0)


class FakeCommands:
    """Answers the probes from a dict, and records every argv it was given."""

    def __init__(self, monkeypatch, module, replies=None, system="Darwin") -> None:
        self.replies = replies or {}
        self.calls: list[list[str]] = []
        monkeypatch.setattr(module.platform, "system", lambda: system)
        monkeypatch.setattr(module.platform, "release", lambda: "1.0")
        monkeypatch.setattr(module.platform, "processor", lambda: "generic-cpu")
        monkeypatch.setattr(module.os, "cpu_count", lambda: 4)
        monkeypatch.setattr(module.subprocess, "run", self._run)

    def _run(self, command, **_kwargs):
        self.calls.append(list(command))
        reply = self.replies.get(self.key(command))
        if isinstance(reply, BaseException):
            raise reply
        if reply is None:  # nothing configured: the binary answered unhappily
            return SimpleNamespace(returncode=1, stdout="", stderr="nope")
        return SimpleNamespace(returncode=0, stdout=reply, stderr="")

    @staticmethod
    def key(command) -> str:
        """`sysctl -n hw.memsize` keys on the leaf; everything else on the binary."""
        return command[-1] if command[0] == "sysctl" else command[0]

    def ran(self, binary: str) -> bool:
        return any(call[0] == binary for call in self.calls)


# What the probes look like on a real Apple Silicon Mac, captured from one.
APPLE_SILICON = {
    "machdep.cpu.brand_string": "Apple M3",
    "hw.physicalcpu": "8",
    "hw.memsize": "17179869184",  # 16 GiB
    "hw.cpufrequency": "",  # genuinely absent on Apple Silicon
    "system_profiler": (
        "Graphics/Displays:\n\n    Apple M3:\n\n"
        "      Chipset Model: Apple M3\n      Type: GPU\n"
        "      Total Number of Cores: 10\n      Vendor: Apple (0x106b)\n"
    ),
}

NVIDIA = {"nvidia-smi": "NVIDIA GeForce RTX 2060, 6144 MiB"}
