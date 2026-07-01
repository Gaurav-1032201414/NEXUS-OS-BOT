"""
performance/resource_guard.py
Monitors system resources in a background thread and exposes guard checks.
Other modules ask "is it safe to run a heavy operation right now?" before doing so.
"""
import threading
import time
import logging
import psutil

logger = logging.getLogger("nexus.guard")


class ResourceGuard:
    """
    Background monitor. Tracks a rolling view of CPU/RAM and lets callers
    gate expensive work (model inference, browser launch, screenshots).
    """

    def __init__(self, cpu_high=85.0, ram_min_gb=1.5, interval=5.0):
        self.cpu_high   = cpu_high
        self.ram_min_gb = ram_min_gb
        self.interval   = interval

        self._lock      = threading.Lock()
        self._snapshot  = {"cpu": 0.0, "ram_avail_gb": 0.0, "ram_pct": 0.0}
        self._running   = False
        self._thread    = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ResourceGuard")
        self._thread.start()
        logger.info("ResourceGuard started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("ResourceGuard stopped")

    def _loop(self):
        while self._running:
            try:
                mem = psutil.virtual_memory()
                cpu = psutil.cpu_percent(interval=1.0)
                with self._lock:
                    self._snapshot = {
                        "cpu": cpu,
                        "ram_avail_gb": round(mem.available / 1e9, 2),
                        "ram_pct": mem.percent,
                    }
            except Exception as e:
                logger.warning(f"Guard loop error: {e}")
            time.sleep(self.interval)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)

    def is_safe(self) -> bool:
        """True if it's safe to run a heavy operation right now."""
        s = self.snapshot()
        if s["cpu"] == 0.0 and s["ram_avail_gb"] == 0.0:
            # Guard not warmed up yet — take a one-off reading
            mem = psutil.virtual_memory()
            return mem.available / 1e9 >= self.ram_min_gb
        return s["cpu"] < self.cpu_high and s["ram_avail_gb"] >= self.ram_min_gb

    def reason_if_unsafe(self) -> str | None:
        """Returns a human-readable reason, or None if safe."""
        s = self.snapshot()
        if s["cpu"] >= self.cpu_high:
            return f"CPU usage is high ({s['cpu']:.0f}%)"
        if 0 < s["ram_avail_gb"] < self.ram_min_gb:
            return f"Low memory ({s['ram_avail_gb']:.1f} GB free)"
        return None
