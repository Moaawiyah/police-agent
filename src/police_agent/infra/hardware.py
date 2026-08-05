"""Best-effort machine facts sealed into the step-zero declaration."""

import os
import platform
import subprocess
from functools import lru_cache

from police_agent.infra.hardware_probes import darwin, nvidia, windows

UNKNOWN = "unknown"
FIELDS = (
    "os", "cpu_type", "cpu_cores", "cpu_freq_mhz", "ram_gb", "gpu_type",
    "gpu_cores_or_cuda", "vram_gb",
)
_TIMEOUT, _SLOW_TIMEOUT = 2.0, 4.0
_BYTES_PER_GB, _MIB_PER_GB = 1024**3, 1024


def hardware_spec() -> dict:
    """Return a defensive copy of the cached hardware declaration."""
    return dict(_probed())


@lru_cache(maxsize=1)
def _probed() -> dict:
    spec = dict.fromkeys(FIELDS, UNKNOWN)
    spec["os"] = f"{platform.system()} {platform.release()}".strip() or UNKNOWN
    spec["cpu_type"] = platform.processor() or UNKNOWN
    spec["cpu_cores"] = os.cpu_count() or UNKNOWN
    system = platform.system()
    if system == "Darwin":
        _darwin(spec)
    elif system == "Windows":
        _windows(spec)
    _nvidia(spec)
    return spec


def _darwin(spec: dict) -> None:
    darwin(spec, _run, _field, _int, _gb, _BYTES_PER_GB, _SLOW_TIMEOUT)


def _windows(spec: dict) -> None:
    windows(spec, _run, _int, _gb, _BYTES_PER_GB)


def _nvidia(spec: dict) -> None:
    nvidia(spec, _run, _int, _gb, _MIB_PER_GB)


def _run(command: list[str], timeout: float = _TIMEOUT) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _field(text: str, label: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(label):
            return stripped[len(label) :].strip()
    return ""


def _int(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _gb(amount: int, per_gb: int):
    return round(amount / per_gb, 1) if amount else UNKNOWN
