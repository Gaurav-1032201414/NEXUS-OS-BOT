"""
os_control/screen_control.py
Screenshots, mouse, keyboard simulation. Uses mss for fast screenshots and
pyautogui for input. Degrades gracefully on headless systems (no DISPLAY).
"""
import os
import time
import logging
from pathlib import Path

logger = logging.getLogger("nexus.screen")

# Detect whether a display is available before importing GUI libs
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
                    or os.name == "nt" or os.uname().sysname == "Darwin"
                    if hasattr(os, "uname") else True)

_pyautogui = None
_mss = None


def _ensure_pyautogui():
    global _pyautogui
    if _pyautogui is None:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True   # move mouse to corner to abort
            pyautogui.PAUSE = 0.1
            _pyautogui = pyautogui
        except Exception as e:
            logger.warning(f"pyautogui unavailable: {e}")
            _pyautogui = False
    return _pyautogui


def _ensure_mss():
    global _mss
    if _mss is None:
        try:
            import mss
            _mss = mss
        except Exception as e:
            logger.warning(f"mss unavailable: {e}")
            _mss = False
    return _mss


def screenshot(save_path: str = None) -> str:
    """Capture the full screen to a PNG. Returns the file path or an error."""
    if not _HAS_DISPLAY:
        return "No display available (headless system) — cannot take screenshot"
    mss_mod = _ensure_mss()
    if not mss_mod:
        return "Screenshot library (mss) not available"

    if save_path is None:
        out_dir = Path("/tmp/nexus_screenshots")
        out_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(out_dir / f"screen_{int(time.time())}.png")

    try:
        with mss_mod.mss() as sct:
            sct.shot(output=save_path)
        return f"Screenshot saved to {save_path}"
    except Exception as e:
        return f"Screenshot failed: {e}"


def screen_size() -> str:
    pg = _ensure_pyautogui()
    if not pg:
        return "pyautogui not available"
    try:
        w, h = pg.size()
        return f"Screen size: {w}x{h}"
    except Exception as e:
        return f"Error: {e}"


def click_at(x: int, y: int, button: str = "left") -> str:
    pg = _ensure_pyautogui()
    if not pg:
        return "Input control not available (headless or pyautogui missing)"
    try:
        pg.click(x=int(x), y=int(y), button=button)
        return f"Clicked {button} at ({x}, {y})"
    except Exception as e:
        return f"Click failed: {e}"


def move_mouse(x: int, y: int, duration: float = 0.3) -> str:
    pg = _ensure_pyautogui()
    if not pg:
        return "Input control not available"
    try:
        pg.moveTo(int(x), int(y), duration=duration)
        return f"Moved mouse to ({x}, {y})"
    except Exception as e:
        return f"Move failed: {e}"


def type_text(text: str, interval: float = 0.02) -> str:
    pg = _ensure_pyautogui()
    if not pg:
        return "Input control not available"
    try:
        pg.typewrite(text, interval=interval)
        return f"Typed {len(text)} characters"
    except Exception as e:
        return f"Type failed: {e}"


def press_key(key: str) -> str:
    pg = _ensure_pyautogui()
    if not pg:
        return "Input control not available"
    try:
        pg.press(key)
        return f"Pressed '{key}'"
    except Exception as e:
        return f"Key press failed: {e}"


def hotkey(*keys: str) -> str:
    """e.g. hotkey('ctrl', 'c') for copy."""
    pg = _ensure_pyautogui()
    if not pg:
        return "Input control not available"
    try:
        pg.hotkey(*keys)
        return f"Pressed hotkey: {'+'.join(keys)}"
    except Exception as e:
        return f"Hotkey failed: {e}"


def scroll(amount: int) -> str:
    """Positive = up, negative = down."""
    pg = _ensure_pyautogui()
    if not pg:
        return "Input control not available"
    try:
        pg.scroll(int(amount))
        return f"Scrolled {amount}"
    except Exception as e:
        return f"Scroll failed: {e}"
