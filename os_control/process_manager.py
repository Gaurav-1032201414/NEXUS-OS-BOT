"""
os_control/process_manager.py
Launch, list, find, and terminate processes. Cross-platform via psutil + platform layer.
"""
import logging
import psutil
from os_control.platform_layer import get_platform

logger = logging.getLogger("nexus.procmgr")


def launch_app(app_name: str) -> str:
    """Launch a GUI application (delegates to platform layer)."""
    return get_platform().open_app(app_name)


def list_processes(limit: int = 20, sort_by: str = "memory") -> str:
    """List running processes, sorted by memory or cpu."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent", "username"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "memory_percent" if sort_by == "memory" else "cpu_percent"
    procs.sort(key=lambda x: x.get(key) or 0, reverse=True)

    lines = [f"Top {limit} processes by {sort_by}:"]
    for p in procs[:limit]:
        lines.append(
            f"  PID {p['pid']:>6}  {(p['name'] or '?')[:25]:<25}  "
            f"MEM {round(p.get('memory_percent') or 0, 1):>4}%  "
            f"CPU {round(p.get('cpu_percent') or 0, 1):>4}%"
        )
    return "\n".join(lines)


def find_process(name: str) -> str:
    """Find processes matching a name substring."""
    matches = []
    for p in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            if name.lower() in (p.info["name"] or "").lower():
                matches.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not matches:
        return f"No process matching '{name}'"
    lines = [f"Found {len(matches)} process(es) matching '{name}':"]
    for p in matches:
        lines.append(f"  PID {p['pid']}  {p['name']}  MEM {round(p.get('memory_percent') or 0,1)}%")
    return "\n".join(lines)


def kill_process(identifier: str) -> str:
    """Kill a process by PID (if numeric) or by name."""
    # By PID
    if identifier.isdigit():
        pid = int(identifier)
        try:
            p = psutil.Process(pid)
            pname = p.name()
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            return f"Terminated process {pid} ({pname})"
        except psutil.NoSuchProcess:
            return f"No process with PID {pid}"
        except psutil.AccessDenied:
            return f"Access denied killing PID {pid} (may need elevated privileges)"
        except Exception as e:
            return f"Error: {e}"

    # By name
    killed = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if identifier.lower() in (p.info["name"] or "").lower():
                p.terminate()
                killed.append(f"{p.info['name']} (PID {p.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        return f"Terminated: {', '.join(killed)}"
    return f"No process matching '{identifier}'"


def process_info(pid: int) -> str:
    """Detailed info about a single process."""
    try:
        p = psutil.Process(int(pid))
        with p.oneshot():
            return (f"PID {pid}: {p.name()}\n"
                    f"  Status: {p.status()}\n"
                    f"  CPU: {p.cpu_percent()}%\n"
                    f"  Memory: {round(p.memory_percent(), 1)}%\n"
                    f"  Threads: {p.num_threads()}\n"
                    f"  Created: {p.create_time()}")
    except psutil.NoSuchProcess:
        return f"No process with PID {pid}"
    except Exception as e:
        return f"Error: {e}"
