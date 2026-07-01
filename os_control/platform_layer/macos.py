"""
os_control/platform_layer/macos.py
macOS implementations using `open`, AppleScript (osascript), and system commands.
Same function signatures as linux.py so the agent code is OS-agnostic.
"""
import subprocess
import logging

logger = logging.getLogger("nexus.platform.macos")

NAME = "Darwin"


def _osascript(script: str) -> str:
    try:
        out = subprocess.check_output(["osascript", "-e", script],
                                      stderr=subprocess.DEVNULL, timeout=10).decode().strip()
        return out
    except Exception as e:
        return f"AppleScript error: {e}"


def open_app(app_name: str) -> str:
    try:
        subprocess.Popen(["open", "-a", app_name],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Launched '{app_name}'"
    except Exception as e:
        return f"Failed to launch '{app_name}': {e}"


def open_url(url: str) -> str:
    try:
        subprocess.Popen(["open", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed: {e}"


def open_file(path: str) -> str:
    try:
        subprocess.Popen(["open", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {path}"
    except Exception as e:
        return f"Failed: {e}"


def list_windows() -> list[str]:
    script = '''
    tell application "System Events"
        set winList to {}
        repeat with proc in (every process whose visible is true)
            repeat with w in (every window of proc)
                set end of winList to name of w
            end repeat
        end repeat
        return winList
    end tell
    '''
    out = _osascript(script)
    return [w.strip() for w in out.split(",") if w.strip()] if out else []


def focus_window(title_substring: str) -> str:
    script = f'tell application "{title_substring}" to activate'
    _osascript(script)
    return f"Attempted to focus '{title_substring}'"


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    _osascript(f"set volume output volume {level}")
    return f"Volume set to {level}%"


def set_brightness(level: int) -> str:
    # macOS brightness needs the `brightness` CLI tool (brew install brightness)
    val = max(0.05, min(1.0, level / 100.0))
    try:
        subprocess.run(["brightness", str(val)], timeout=5)
        return f"Brightness set to {level}%"
    except FileNotFoundError:
        return "Install brightness tool: brew install brightness"
    except Exception as e:
        return f"Failed: {e}"


def notify(title: str, message: str) -> str:
    _osascript(f'display notification "{message}" with title "{title}"')
    return "Notification sent"


def lock_screen() -> str:
    try:
        subprocess.run(["pmset", "displaysleepnow"], timeout=5)
        return "Screen locked"
    except Exception as e:
        return f"Failed: {e}"
