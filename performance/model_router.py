"""
performance/model_router.py
Chooses the best local Ollama model at runtime based on current hardware state.
Falls back to cloud (OpenAI) when resources are critically low.
"""
import time
import logging
import psutil

logger = logging.getLogger("nexus.router")

# Model profiles: key → Ollama model string
# Edit these to match models you've pulled via `ollama pull`
PROFILES = {
    "light":  "phi3:mini",       # ~1.7 GB — for 4-8 GB RAM systems
    "medium": "llama3.2:3b",     # ~2.0 GB — for 8-12 GB RAM
    "full":   "llama3.1:8b",     # ~4.7 GB — for 16 GB+ RAM
    "cloud":  "gpt-4o-mini",     # OpenAI fallback — requires OPENAI_API_KEY
}

# Which profiles actually need to exist locally
LOCAL_PROFILES = ["light", "medium", "full"]


class ModelRouter:
    """
    Inspects CPU, RAM, and GPU in real time and picks the best available model.
    Caches the decision for `cache_ttl` seconds to avoid constant re-checking.
    """

    def __init__(self, cache_ttl: int = 30):
        self.cache_ttl   = cache_ttl
        self._last_check = 0
        self._cached     = None
        self._available  = set()  # models confirmed available in Ollama
        self._refresh_available()

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def best_model(self, force_refresh: bool = False) -> str:
        """Return the name of the best model to use right now."""
        now = time.monotonic()
        if force_refresh or self._cached is None or (now - self._last_check) > self.cache_ttl:
            self._cached     = self._select()
            self._last_check = now
        return self._cached

    def profile_name(self) -> str:
        """Return the profile key ('light', 'medium', 'full', 'cloud')."""
        model = self.best_model()
        for k, v in PROFILES.items():
            if v == model:
                return k
        return "unknown"

    def report(self) -> dict:
        """Diagnostic dictionary — useful for the /status API endpoint."""
        mem      = psutil.virtual_memory()
        cpu      = psutil.cpu_percent(interval=0.3)
        selected = self.best_model()
        return {
            "selected_model":  selected,
            "profile":         self.profile_name(),
            "cpu_percent":     cpu,
            "ram_avail_gb":    round(mem.available / 1e9, 2),
            "ram_total_gb":    round(mem.total     / 1e9, 2),
            "available_models": list(self._available),
        }

    # ──────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────

    def _select(self) -> str:
        mem       = psutil.virtual_memory()
        cpu_pct   = psutil.cpu_percent(interval=0.5)
        ram_avail = mem.available / 1e9   # GB

        logger.debug(f"Router: cpu={cpu_pct:.0f}% ram_avail={ram_avail:.1f}GB")

        # System critically under load → lightest possible model
        if cpu_pct > 85 or ram_avail < 1.5:
            return self._pick(["light", "cloud"])

        # Try full → medium → light based on available RAM
        if ram_avail >= 10:
            return self._pick(["full", "medium", "light", "cloud"])
        elif ram_avail >= 5:
            return self._pick(["medium", "light", "cloud"])
        else:
            return self._pick(["light", "cloud"])

    def _pick(self, preference_order: list) -> str:
        """Return first model in preference_order that is actually available."""
        for key in preference_order:
            model = PROFILES.get(key)
            if not model:
                continue
            if key == "cloud":
                return model   # Cloud always "available" (may fail at call time)
            if model in self._available:
                return model

        # Last resort: return light even if not confirmed available
        return PROFILES["light"]

    def _refresh_available(self):
        """Query Ollama for locally pulled models."""
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                self._available = {m["name"] for m in models}
                logger.info(f"Ollama available: {self._available}")
                return
        except Exception as e:
            logger.warning(f"Could not query Ollama: {e}")

        # Fallback: assume light model is available
        self._available = {PROFILES["light"]}
