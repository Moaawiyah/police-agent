"""Platform-specific hardware probes used by ``infra.hardware``."""

import json

WINDOWS_QUERY = (
    "$p=Get-CimInstance Win32_Processor|Select-Object -First 1;"
    "$s=Get-CimInstance Win32_ComputerSystem;"
    "$v=Get-CimInstance Win32_VideoController|Select-Object -First 1;"
    "@{cpu=$p.Name;mhz=$p.MaxClockSpeed;cores=$p.NumberOfCores;"
    "ram=$s.TotalPhysicalMemory;gpu=$v.Name;vram=$v.AdapterRAM}|ConvertTo-Json -Compress"
)


def darwin(spec, run, field, number, gigabytes, bytes_per_gb, slow_timeout) -> None:
    spec["cpu_type"] = run(["sysctl", "-n", "machdep.cpu.brand_string"]) or spec["cpu_type"]
    spec["cpu_cores"] = number(run(["sysctl", "-n", "hw.physicalcpu"])) or spec["cpu_cores"]
    spec["ram_gb"] = gigabytes(number(run(["sysctl", "-n", "hw.memsize"])), bytes_per_gb)
    hertz = number(run(["sysctl", "-n", "hw.cpufrequency"]))
    if hertz:
        spec["cpu_freq_mhz"] = round(hertz / 1_000_000)
    display = run(["system_profiler", "SPDisplaysDataType"], timeout=slow_timeout)
    spec["gpu_type"] = field(display, "Chipset Model:") or spec["gpu_type"]
    spec["gpu_cores_or_cuda"] = number(field(display, "Total Number of Cores:")) or "unknown"


def windows(spec, run, number, gigabytes, bytes_per_gb) -> None:
    try:
        found = json.loads(run(["powershell", "-NoProfile", "-Command", WINDOWS_QUERY]) or "{}")
    except ValueError:
        return
    spec["cpu_type"] = found.get("cpu") or spec["cpu_type"]
    spec["cpu_freq_mhz"] = number(found.get("mhz")) or spec["cpu_freq_mhz"]
    spec["cpu_cores"] = number(found.get("cores")) or spec["cpu_cores"]
    spec["ram_gb"] = gigabytes(number(found.get("ram")), bytes_per_gb)
    spec["gpu_type"] = found.get("gpu") or spec["gpu_type"]
    spec["vram_gb"] = gigabytes(number(found.get("vram")), bytes_per_gb)


def nvidia(spec, run, number, gigabytes, mib_per_gb) -> None:
    reply = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if not reply:
        return
    name, _, memory = reply.splitlines()[0].partition(",")
    spec["gpu_type"] = name.strip() or spec["gpu_type"]
    spec["vram_gb"] = gigabytes(number(memory.replace("MiB", "")), mib_per_gb) or spec["vram_gb"]
    spec["gpu_cores_or_cuda"] = "CUDA (core count not exposed by driver)"
