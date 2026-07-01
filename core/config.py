"""
core/config.py
Loads config.json, expands ~ paths, ensures data directories exist.
Single source of truth for all settings across the app.
"""
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger("nexus.config")

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class Config:
    """Wraps the config dict with dotted-path access and path expansion."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else _DEFAULT_CONFIG_PATH
        self._data = self._load()
        self._ensure_dirs()

    def _load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config not found at {self.path}, using built-in defaults")
            return self._defaults()
        except json.JSONDecodeError as e:
            logger.error(f"Config JSON invalid: {e}, using defaults")
            return self._defaults()

    def _defaults(self) -> dict:
        return {
            "ollama": {"host": "http://localhost:11434", "timeout": 120},
            "memory": {"db_path": "~/.nexus/memory.db", "max_history_turns": 20},
            "performance": {"cpu_high_threshold": 85, "ram_minimum_gb": 1.5},
            "os_control": {"screenshot_path": "/tmp/nexus_screenshots", "pyautogui_pause": 0.1},
            "api": {"host": "127.0.0.1", "port": 8765},
            "logging": {"level": "INFO", "file": "~/.nexus/nexus.log"},
        }

    def get(self, dotted_key: str, default=None):
        """Access nested keys: config.get('ollama.host')"""
        node = self._data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def path_for(self, dotted_key: str, default=None) -> Path:
        """Get a config value as an expanded Path (handles ~)."""
        raw = self.get(dotted_key, default)
        if raw is None:
            return None
        return Path(os.path.expanduser(str(raw)))

    def _ensure_dirs(self):
        """Create the ~/.nexus dir and any configured output dirs."""
        nexus_home = Path(os.path.expanduser("~/.nexus"))
        nexus_home.mkdir(parents=True, exist_ok=True)

        for key in ["memory.db_path", "memory.vector_db_path",
                    "logging.file", "os_control.screenshot_path"]:
            p = self.path_for(key)
            if p:
                # If it's a file path, make the parent; if dir, make it
                if p.suffix:  # has extension → file
                    p.parent.mkdir(parents=True, exist_ok=True)
                else:
                    p.mkdir(parents=True, exist_ok=True)

    @property
    def data(self) -> dict:
        return self._data


# Singleton accessor
_instance = None

def get_config(path=None) -> Config:
    global _instance
    if _instance is None:
        _instance = Config(path)
    return _instance
