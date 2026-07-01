"""
performance/hardware_probe.py
Probes the system hardware: CPU, RAM, disk, GPU.
Works on Linux, macOS, and Windows without any changes.
"""
import platform
import subprocess
import psutil
import logging

logger = logging.getLogger("nexus.hardware")


def probe() -> dict:
    """
    Returns a full snapshot of current hardware state.
    All values are safe to call repeatedly — nothing mutates state.
    """
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_freq = psutil.cpu_freq()

    result = {
        "os":             platform.system(),
        "os_version":     platform.version(),
        "os_release":     platform.release(),
        "machine":        platform.machine(),
        "python_version": platform.python_version(),
        "cpu_cores_logical":  psutil.cpu_count(logical=True),
        "cpu_cores_physical": psutil.cpu_count(logical=False) or 1,
        "cpu_freq_mhz":   round(cpu_freq.current, 0) if cpu_freq else 0,
        "cpu_percent":    psutil.cpu_percent(interval=0.5),
        "ram_total_gb":   round(mem.total    / 1e9, 2),
        "ram_used_gb":    round(mem.used     / 1e9, 2),
        "ram_avail_gb":   round(mem.available / 1e9, 2),
        "ram_percent":    mem.percent,
        "disk_total_gb":  round(disk.total / 1e9, 1),
        "disk_free_gb":   round(disk.free  / 1e9, 1),
        "disk_percent":   disk.percent,
        "gpu_vram_free_gb": 0.0,
        "gpu_name":       "none",
        "has_gpu":        False,
    }

    # GPU detection — try nvidia-smi first (most common on Linux)
    gpu_info = _detect_gpu()
    result.update(gpu_info)

    return result


def _detect_gpu() -> dict:
    """Try multiple methods to detect GPU. Returns safe defaults on failure."""
    # Method 1: nvidia-smi (NVIDIA GPUs)
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=5
        ).decode().strip().split("\n")[0]

        parts = [p.strip() for p in out.split(",")]
        if len(parts) >= 3:
            name     = parts[0]
            free_mb  = float(parts[1])
            total_mb = float(parts[2])
            return {
                "gpu_name":        name,
                "gpu_vram_free_gb": round(free_mb  / 1024, 2),
                "gpu_vram_gb":      round(total_mb / 1024, 2),
                "has_gpu":          True,
                "gpu_type":         "nvidia",
            }
    except Exception:
        pass

    # Method 2: GPUtil python library
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            return {
                "gpu_name":         g.name,
                "gpu_vram_free_gb": round(g.memoryFree  / 1024, 2),
                "gpu_vram_gb":      round(g.memoryTotal / 1024, 2),
                "has_gpu":          True,
                "gpu_type":         "nvidia",
            }
    except Exception:
        pass

    # Method 3: ROCm (AMD)
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        import json
        data = json.loads(out)
        # ROCm format varies; just flag GPU presence
        return {"has_gpu": True, "gpu_type": "amd", "gpu_name": "AMD GPU"}
    except Exception:
        pass

    return {"has_gpu": False, "gpu_name": "none", "gpu_vram_free_gb": 0.0}


def get_system_summary() -> str:
    """Human-readable summary for injecting into the agent's system prompt."""
    p = probe()
    lines = [
        f"OS: {p['os']} {p['os_release']}",
        f"CPU: {p['cpu_cores_physical']} cores ({p['cpu_cores_logical']} logical) @ {p['cpu_freq_mhz']} MHz",
        f"RAM: {p['ram_avail_gb']} GB free of {p['ram_total_gb']} GB total",
        f"Disk: {p['disk_free_gb']} GB free of {p['disk_total_gb']} GB total",
    ]
    if p["has_gpu"]:
        lines.append(f"GPU: {p['gpu_name']} — {p.get('gpu_vram_free_gb', 0)} GB VRAM free")
    else:
        lines.append("GPU: Not detected (CPU-only mode)")
    return " | ".join(lines)
