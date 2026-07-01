"""
os_control/platform_layer/linux.py
Linux-specific implementations. Uses subprocess + common Linux tools
(xdotool, wmctrl, amixer, xdg-open). All functions degrade gracefully
if the underlying tool is missing.
"""
import subprocess
import shutil
import logging

logger = logging.getLogger("nexus.platform.linux")

NAME = "Linux"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def open_app(app_name: str) -> str:
    """Launch an application by command name or .desktop name."""
    try:
        # Prefer gtk-launch for .desktop entries, fall back to direct exec
        if _have("gtk-launch"):
            subprocess.Popen(["gtk-launch", app_name],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        else:
            subprocess.Popen([app_name],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        return f"Launched '{app_name}'"
    except FileNotFoundError:
        return f"Application '{app_name}' not found"
    except Exception as e:
        return f"Failed to launch '{app_name}': {e}"


def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    try:
        subprocess.Popen(["xdg-open", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed to open URL: {e}"


def open_file(path: str) -> str:
    """Open a file with its default associated application."""
    try:
        subprocess.Popen(["xdg-open", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {path}"
    except Exception as e:
        return f"Failed to open file: {e}"


def list_windows() -> list[str]:
    """Return titles of open windows via wmctrl."""
    if not _have("wmctrl"):
        return ["wmctrl not installed — run: sudo apt install wmctrl"]
    try:
        out = subprocess.check_output(["wmctrl", "-l"], timeout=5).decode()
        titles = []
        for line in out.strip().split("\n"):
            if line.strip():
                parts = line.split(None, 3)
                titles.append(parts[-1] if len(parts) >= 4 else line)
        return titles
    except Exception as e:
        return [f"Error listing windows: {e}"]


def focus_window(title_substring: str) -> str:
    """Bring a window matching the title to the front."""
    if not _have("wmctrl"):
        return "wmctrl not installed"
    try:
        subprocess.run(["wmctrl", "-a", title_substring], timeout=5, check=True)
        return f"Focused window matching '{title_substring}'"
    except subprocess.CalledProcessError:
        return f"No window matching '{title_substring}'"
    except Exception as e:
        return f"Error: {e}"


def set_volume(level: int) -> str:
    """Set master volume 0-100 via amixer (ALSA/PulseAudio)."""
    level = max(0, min(100, int(level)))
    if _have("amixer"):
        try:
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return f"Volume set to {level}%"
        except Exception:
            pass
    if _have("pactl"):
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return f"Volume set to {level}%"
        except Exception as e:
            return f"Failed to set volume: {e}"
    return "No volume tool (amixer/pactl) found"


def set_brightness(level: int) -> str:
    """Set screen brightness 0-100 via brightnessctl or xrandr."""
    level = max(5, min(100, int(level)))
    if _have("brightnessctl"):
        try:
            subprocess.run(["brightnessctl", "set", f"{level}%"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return f"Brightness set to {level}%"
        except Exception as e:
            return f"Failed: {e}"
    return "brightnessctl not installed"


def notify(title: str, message: str) -> str:
    """Send a desktop notification."""
    if _have("notify-send"):
        try:
            subprocess.run(["notify-send", title, message], timeout=5)
            return "Notification sent"
        except Exception as e:
            return f"Failed: {e}"
    return "notify-send not installed"


def lock_screen() -> str:
    for cmd in (["loginctl", "lock-session"],
                ["xdg-screensaver", "lock"],
                ["gnome-screensaver-command", "-l"]):
        if _have(cmd[0]):
            try:
                subprocess.run(cmd, timeout=5)
                return "Screen locked"
            except Exception:
                continue
    return "No screen-lock tool found"
