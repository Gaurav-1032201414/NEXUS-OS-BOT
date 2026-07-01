"""
os_control/clipboard.py
Read and write the system clipboard via pyperclip.
Falls back gracefully on headless systems.
"""
import logging

logger = logging.getLogger("nexus.clipboard")

_pyperclip = None


def _ensure():
    global _pyperclip
    if _pyperclip is None:
        try:
            import pyperclip
            # Trigger a probe so we fail early if no backend
            _pyperclip = pyperclip
        except Exception as e:
            logger.warning(f"pyperclip unavailable: {e}")
            _pyperclip = False
    return _pyperclip


def get_clipboard() -> str:
    pc = _ensure()
    if not pc:
        return "Clipboard not available (install xclip/xsel on Linux)"
    try:
        content = pc.paste()
        return content if content else "(clipboard is empty)"
    except Exception as e:
        return f"Clipboard read failed: {e} (on Linux, install: sudo apt install xclip)"


def set_clipboard(text: str) -> str:
    pc = _ensure()
    if not pc:
        return "Clipboard not available (install xclip/xsel on Linux)"
    try:
        pc.copy(text)
        return f"Copied {len(text)} characters to clipboard"
    except Exception as e:
        return f"Clipboard write failed: {e}"
