"""
os_control/index_watcher.py
Background thread that periodically rescans the user's directories and updates
the cached index only when files/folders have actually changed.

Lightweight by design: it runs on an interval (default 5 min), and the scan
itself is bounded by directory_index's depth/entry caps. When a change is
detected, it fires an optional callback so the agent can refresh its prompt.
"""
import threading
import time
import logging

from os_control import directory_index

logger = logging.getLogger("nexus.indexwatcher")


class IndexWatcher:
    def __init__(self, interval_seconds: int = 300, on_change=None):
        """
        interval_seconds: how often to rescan (default 300 = 5 minutes)
        on_change: optional callback(diff_dict) called when changes are found.
                   diff_dict = {"added": [...], "removed": [...], "index": {...}}
        """
        self.interval   = max(30, int(interval_seconds))  # floor of 30s
        self.on_change  = on_change
        self._running   = False
        self._thread    = None
        self._last_diff = {"added": [], "removed": [], "changed": False}
        self._lock      = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="IndexWatcher")
        self._thread.start()
        logger.info(f"IndexWatcher started (interval={self.interval}s)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("IndexWatcher stopped")

    def _loop(self):
        # Don't scan immediately on start — the agent already builds/loads the
        # index at startup. Wait one interval, then begin periodic checks.
        while self._running:
            for _ in range(self.interval):
                if not self._running:
                    return
                time.sleep(1)
            try:
                self._check()
            except Exception as e:
                logger.warning(f"IndexWatcher scan error: {e}")

    def _check(self):
        result = directory_index.refresh_if_changed()
        with self._lock:
            self._last_diff = {
                "added":   result["added"],
                "removed": result["removed"],
                "changed": result["changed"],
            }
        if result["changed"]:
            logger.info(
                f"Filesystem change detected: +{len(result['added'])} "
                f"-{len(result['removed'])} items"
            )
            if self.on_change:
                try:
                    self.on_change(result)
                except Exception as e:
                    logger.warning(f"on_change callback failed: {e}")

    def force_check(self) -> dict:
        """Trigger an immediate change check (outside the interval)."""
        self._check()
        return self.last_diff()

    def last_diff(self) -> dict:
        with self._lock:
            return dict(self._last_diff)
