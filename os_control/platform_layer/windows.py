"""
os_control/platform_layer/windows.py
Windows implementations using os.startfile, PowerShell, and ctypes.
Same function signatures as linux.py / macos.py.
"""
import subprocess
import os
import logging

logger = logging.getLogger("nexus.platform.windows")

NAME = "Windows"


def _powershell(cmd: str) -> str:
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            stderr=subprocess.DEVNULL, timeout=10
        ).decode(errors="ignore").strip()
        return out
    except Exception as e:
        return f"PowerShell error: {e}"


def open_app(app_name: str) -> str:
    try:
        subprocess.Popen(["start", "", app_name], shell=True)
        return f"Launched '{app_name}'"
    except Exception as e:
        return f"Failed to launch '{app_name}': {e}"


def open_url(url: str) -> str:
    try:
        os.startfile(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed: {e}"


def open_file(path: str) -> str:
    try:
        os.startfile(path)
        return f"Opened {path}"
    except Exception as e:
        return f"Failed: {e}"


def list_windows() -> list[str]:
    cmd = ("Get-Process | Where-Object {$_.MainWindowTitle -ne ''} "
           "| Select-Object -ExpandProperty MainWindowTitle")
    out = _powershell(cmd)
    return [l.strip() for l in out.split("\n") if l.strip()] if out else []


def focus_window(title_substring: str) -> str:
    # Uses the WScript shell AppActivate
    cmd = f'(New-Object -ComObject WScript.Shell).AppActivate("{title_substring}")'
    _powershell(cmd)
    return f"Attempted to focus '{title_substring}'"


def set_volume(level: int) -> str:
    # Windows volume control via nircmd if present, else report
    level = max(0, min(100, int(level)))
    raw = int(level / 100 * 65535)
    try:
        subprocess.run(["nircmd.exe", "setsysvolume", str(raw)], timeout=5)
        return f"Volume set to {level}%"
    except FileNotFoundError:
        return "Volume control needs nircmd.exe in PATH"
    except Exception as e:
        return f"Failed: {e}"


def set_brightness(level: int) -> str:
    level = max(0, min(100, int(level)))
    cmd = (f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
           f".WmiSetBrightness(1,{level})")
    _powershell(cmd)
    return f"Brightness set to {level}%"


def notify(title: str, message: str) -> str:
    cmd = (f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, '
           f'ContentType=WindowsRuntime] | Out-Null; Write-Output "{title}: {message}"')
    _powershell(cmd)
    return "Notification sent"


def lock_screen() -> str:
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
        return "Screen locked"
    except Exception as e:
        return f"Failed: {e}"
