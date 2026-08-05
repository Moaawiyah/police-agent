"""What machine this agent is playing on, for the signed step-zero declaration.

The specification asks for this because the league is scored on *computational
fairness* (ch. 5.5): a clever algorithm on a modest laptop is meant to outrank a
wasteful one on a server farm, and the grader can only apply that normalisation
if each peer declares what it ran on. Appendix He rule 24 makes the declaration
mandatory, with the fairness bonus as the stake.

Every value here is best effort and every probe is allowed to fail. A missing
figure becomes the literal string `"unknown"` rather than a guess or an
exception: the declaration is sealed and published before the first move, so a
probe that raised would cost the match, and a number that was invented would be
a false statement in a document this peer cryptographically signs.

That tolerance is why this lives in `infra/` beside `ngrok_agent.py` rather than
in `shared/` -- it shells out to foreign binaries whose presence, version and
output format are all outside our control.
"""

import os
import platform
import subprocess
from functools import lru_cache

UNKNOWN = "unknown"

# Every spec carries all eight keys, present or not, so the consumer never has
# to branch on absence and the sealed payload has a fixed shape.
FIELDS = (
    "os",
    "cpu_type",
    "cpu_cores",
    "cpu_freq_mhz",
    "ram_gb",
    "gpu_type",
    "gpu_cores_or_cuda",
    "vram_gb",
)

# Short, because this runs before the handshake while the opponent's watchdog is
# not yet ticking -- but a wedged `system_profiler` must not become our timeout.
_TIMEOUT = 2.0
_SLOW_TIMEOUT = 4.0

_BYTES_PER_GB = 1024**3
_MIB_PER_GB = 1024

_WINDOWS_QUERY = (
    "$p=Get-CimInstance Win32_Processor|Select-Object -First 1;"
    "$s=Get-CimInstance Win32_ComputerSystem;"
    "$v=Get-CimInstance Win32_VideoController|Select-Object -First 1;"
    "@{cpu=$p.Name;mhz=$p.MaxClockSpeed;cores=$p.NumberOfCores;"
    "ram=$s.TotalPhysicalMemory;gpu=$v.Name;vram=$v.AdapterRAM}|ConvertTo-Json -Compress"
)


def hardware_spec() -> dict:
    """This machine's specification, probed once and reused.

    A copy, so a caller that folds it into a payload cannot mutate what the next
    caller sees -- the same dict ends up inside a sealed record.
    """
    return dict(_probed())


@lru_cache(maxsize=1)
def _probed() -> dict:
    """The real work, cached: probing costs subprocesses and never changes."""
    spec = dict.fromkeys(FIELDS, UNKNOWN)
    spec["os"] = f"{platform.system()} {platform.release()}".strip() or UNKNOWN
    spec["cpu_type"] = platform.processor() or UNKNOWN
    spec["cpu_cores"] = os.cpu_count() or UNKNOWN

    system = platform.system()
    if system == "Darwin":
        _darwin(spec)
    elif system == "Windows":
        _windows(spec)
    # Linux keeps the platform/os.cpu_count() answers above; there is no portable
    # probe worth shelling out for, and /proc parsing would be its own module.

    _nvidia(spec)  # every platform: an NVIDIA card overrides whatever was found
    return spec


def _darwin(spec: dict) -> None:
    """macOS via sysctl and system_profiler.

    `hw.cpufrequency` is absent on Apple Silicon and the brand string carries no
    clock either, so `cpu_freq_mhz` stays "unknown" on those machines. That is
    the honest answer: the figure genuinely is not exposed.
    """
    spec["cpu_type"] = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or spec["cpu_type"]
    spec["cpu_cores"] = _int(_run(["sysctl", "-n", "hw.physicalcpu"])) or spec["cpu_cores"]
    spec["ram_gb"] = _gb(_int(_run(["sysctl", "-n", "hw.memsize"])), _BYTES_PER_GB)
    hertz = _int(_run(["sysctl", "-n", "hw.cpufrequency"]))
    if hertz:
        spec["cpu_freq_mhz"] = round(hertz / 1_000_000)

    display = _run(["system_profiler", "SPDisplaysDataType"], timeout=_SLOW_TIMEOUT)
    spec["gpu_type"] = _field(display, "Chipset Model:") or spec["gpu_type"]
    spec["gpu_cores_or_cuda"] = _int(_field(display, "Total Number of Cores:")) or UNKNOWN
    # VRAM is deliberately left unknown on unified memory: the GPU has no
    # separate pool to report, and repeating `ram_gb` here would overstate it.


def _windows(spec: dict) -> None:
    """Windows via one PowerShell round trip rather than four."""
    import json

    try:
        found = json.loads(_run(["powershell", "-NoProfile", "-Command", _WINDOWS_QUERY]) or "{}")
    except ValueError:
        return
    spec["cpu_type"] = found.get("cpu") or spec["cpu_type"]
    spec["cpu_freq_mhz"] = _int(found.get("mhz")) or spec["cpu_freq_mhz"]
    spec["cpu_cores"] = _int(found.get("cores")) or spec["cpu_cores"]
    spec["ram_gb"] = _gb(_int(found.get("ram")), _BYTES_PER_GB)
    spec["gpu_type"] = found.get("gpu") or spec["gpu_type"]
    spec["vram_gb"] = _gb(_int(found.get("vram")), _BYTES_PER_GB)


def _nvidia(spec: dict) -> None:
    """An NVIDIA card, if one answers -- the one probe worth running everywhere.

    It runs last and overrides on purpose: Win32_VideoController reports VRAM
    through a 32-bit field that saturates at 4 GB, so the driver's own figure is
    the more truthful of the two.
    """
    reply = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if not reply:
        return
    name, _, memory = reply.splitlines()[0].partition(",")
    spec["gpu_type"] = name.strip() or spec["gpu_type"]
    spec["vram_gb"] = _gb(_int(memory.replace("MiB", "")), _MIB_PER_GB) or spec["vram_gb"]
    spec["gpu_cores_or_cuda"] = "CUDA (core count not exposed by driver)"


def _run(command: list[str], timeout: float = _TIMEOUT) -> str:
    """One probe. Any failure at all is an empty string, never an exception."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""  # binary missing, not executable, or wedged past the timeout
    return done.stdout.strip() if done.returncode == 0 else ""


def _field(text: str, label: str) -> str:
    """The value after `label` in indented `key: value` output."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(label):
            return stripped[len(label) :].strip()
    return ""


def _int(value) -> int:
    """A whole number, or 0 for anything that is not one."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _gb(amount: int, per_gb: int):
    """Rounded gigabytes, or "unknown" when the source had nothing to say."""
    return round(amount / per_gb, 1) if amount else UNKNOWN
