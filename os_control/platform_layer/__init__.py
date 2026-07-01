"""
os_control/platform_layer/__init__.py
Selects the correct platform implementation at runtime.
Every platform module (linux/macos/windows) exposes the SAME function names,
so the rest of the app never has to branch on OS.
"""
import platform
import importlib
import logging

logger = logging.getLogger("nexus.platform")

_PLATFORM_MAP = {
    "Linux":   "linux",
    "Darwin":  "macos",
    "Windows": "windows",
}

_cached_module = None


def get_platform():
    """Return the platform-specific module for the current OS."""
    global _cached_module
    if _cached_module is not None:
        return _cached_module

    os_name = platform.system()
    mod_name = _PLATFORM_MAP.get(os_name, "linux")
    try:
        _cached_module = importlib.import_module(
            f".{mod_name}", package="os_control.platform_layer"
        )
        logger.info(f"Loaded platform module: {mod_name}")
    except ImportError as e:
        logger.error(f"Failed to load platform module {mod_name}: {e}")
        # Fall back to linux as a safe default
        _cached_module = importlib.import_module(
            ".linux", package="os_control.platform_layer"
        )
    return _cached_module


def current_os() -> str:
    return platform.system()
