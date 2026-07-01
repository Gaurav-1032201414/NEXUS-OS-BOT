"""
os_control/system_info.py
Gathers a complete picture of the host system: OS, hardware, installed apps,
running processes, network, users. This is what gives NEXUS "understanding"
of the environment it lives in.
"""
import platform
import socket
import getpass
import os
import shutil
import subprocess
import logging
from pathlib import Path
import psutil

logger = logging.getLogger("nexus.sysinfo")


def full_scan() -> dict:
    """Complete system snapshot. Run once at startup; cache in memory facts."""
    return {
        "identity":   _identity(),
        "hardware":   _hardware(),
        "os":         _os_details(),
        "network":    _network(),
        "storage":    _storage(),
        "top_processes": top_processes(5),
    }


def _identity() -> dict:
    return {
        "hostname": socket.gethostname(),
        "user":     getpass.getuser(),
        "home":     str(Path.home()),
        "cwd":      os.getcwd(),
        "shell":    os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown")),
    }


def _hardware() -> dict:
    mem  = psutil.virtual_memory()
    swap = psutil.swap_memory()
    freq = psutil.cpu_freq()
    return {
        "cpu_model":      _cpu_model(),
        "cpu_physical":   psutil.cpu_count(logical=False) or 1,
        "cpu_logical":    psutil.cpu_count(logical=True),
        "cpu_freq_mhz":   round(freq.current) if freq else 0,
        "ram_total_gb":   round(mem.total / 1e9, 2),
        "ram_available_gb": round(mem.available / 1e9, 2),
        "swap_total_gb":  round(swap.total / 1e9, 2),
    }


def _cpu_model() -> str:
    try:
        import cpuinfo
        return cpuinfo.get_cpu_info().get("brand_raw", platform.processor())
    except Exception:
        # Linux fallback: read /proc/cpuinfo
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return platform.processor() or "Unknown CPU"


def _os_details() -> dict:
    return {
        "system":   platform.system(),
        "release":  platform.release(),
        "version":  platform.version(),
        "machine":  platform.machine(),
        "distro":   _linux_distro(),
        "python":   platform.python_version(),
        "boot_time": _boot_time(),
    }


def _linux_distro() -> str:
    if platform.system() != "Linux":
        return platform.system()
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "Linux"


def _boot_time() -> str:
    import datetime
    return datetime.datetime.fromtimestamp(psutil.boot_time()).isoformat(timespec="seconds")


def _network() -> dict:
    info = {"hostname": socket.gethostname(), "interfaces": {}}
    try:
        info["local_ip"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["local_ip"] = "unknown"
    try:
        for name, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET:
                    info["interfaces"][name] = a.address
    except Exception:
        pass
    return info


def _storage() -> list[dict]:
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device":     part.device,
                "mountpoint": part.mountpoint,
                "fstype":     part.fstype,
                "total_gb":   round(usage.total / 1e9, 1),
                "free_gb":    round(usage.free / 1e9, 1),
                "percent":    usage.percent,
            })
        except (PermissionError, OSError):
            continue
    return disks


def top_processes(n: int = 10) -> list[dict]:
    """Top n processes by memory usage."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            procs.append({
                "pid":  p.info["pid"],
                "name": p.info["name"],
                "mem_pct": round(p.info["memory_percent"] or 0, 1),
                "cpu_pct": round(p.info["cpu_percent"] or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["mem_pct"], reverse=True)
    return procs[:n]


def find_installed_apps() -> list[str]:
    """Best-effort list of installed GUI applications (Linux .desktop scan)."""
    apps = set()
    if platform.system() == "Linux":
        for d in ["/usr/share/applications",
                  str(Path.home() / ".local/share/applications")]:
            p = Path(d)
            if p.exists():
                for f in p.glob("*.desktop"):
                    apps.add(f.stem)
    elif platform.system() == "Darwin":
        for d in ["/Applications", str(Path.home() / "Applications")]:
            p = Path(d)
            if p.exists():
                for f in p.glob("*.app"):
                    apps.add(f.stem)
    return sorted(apps)


def summary_text() -> str:
    """One-paragraph summary for the agent's system prompt."""
    s = full_scan()
    hw, osd, ident = s["hardware"], s["os"], s["identity"]
    return (
        f"Host '{ident['hostname']}' running {osd['distro']} ({osd['system']} "
        f"{osd['release']}). User: {ident['user']}, home: {ident['home']}. "
        f"CPU: {hw['cpu_model']} ({hw['cpu_physical']} cores). "
        f"RAM: {hw['ram_available_gb']}/{hw['ram_total_gb']} GB free. "
        f"Shell: {ident['shell']}."
    )
