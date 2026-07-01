"""
tray.py
Phase 6 (quick win) — system tray icon. Pure Python via pystray.
Lives in the tray on Linux/macOS/Windows. Menu lets you:
  - Start/stop the FastAPI server (so the UI can connect)
  - Trigger a voice push-to-talk
  - Open the web UI
  - Check status / quit

Run:  python tray.py
"""
import sys
import threading
import logging
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("nexus.tray")


def _make_icon_image():
    """Generate a simple 64x64 'NX' icon in memory."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (8, 12, 16, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, 59, 59], outline=(0, 229, 255, 255), width=2)
    d.text((14, 22), "NX", fill=(0, 229, 255, 255))
    return img


class NexusTray:
    def __init__(self):
        self.agent       = None
        self.api_thread  = None
        self.voice_loop  = None
        self._api_running = False

    # ── Lazy agent ──
    def _get_agent(self):
        if self.agent is None:
            from core.agent import NexusAgent
            self.agent = NexusAgent()
        return self.agent

    # ── Menu actions ──
    def start_api(self, icon, item):
        if self._api_running:
            self._notify(icon, "API already running on :8765")
            return
        def run():
            import uvicorn
            from api.server import app
            from core.config import get_config
            cfg = get_config()
            uvicorn.run(app, host=cfg.get("api.host", "127.0.0.1"),
                        port=cfg.get("api.port", 8765), log_level="warning")
        self.api_thread = threading.Thread(target=run, daemon=True, name="NexusAPI")
        self.api_thread.start()
        self._api_running = True
        self._notify(icon, "NEXUS API started on http://127.0.0.1:8765")

    def open_ui(self, icon, item):
        webbrowser.open("http://127.0.0.1:8765/api/health")

    def voice_ptt(self, icon, item):
        def run():
            from voice.voice_loop import VoiceLoop, diagnostics
            if not all(diagnostics().values()):
                self._notify(icon, "Voice deps not installed")
                return
            if self.voice_loop is None:
                self.voice_loop = VoiceLoop(self._get_agent())
            self.voice_loop.push_to_talk()
        threading.Thread(target=run, daemon=True).start()
        self._notify(icon, "Listening... speak now")

    def show_status(self, icon, item):
        try:
            h = self._get_agent().health()
            msg = (f"Ollama: {'online' if h['ollama_alive'] else 'offline'} | "
                   f"Model: {h['router']['selected_model']} | "
                   f"Tools: {h['tools_loaded']}")
        except Exception as e:
            msg = f"Status error: {e}"
        self._notify(icon, msg)

    def quit(self, icon, item):
        if self.agent:
            self.agent.shutdown()
        icon.stop()

    def _notify(self, icon, message):
        logger.info(message)
        try:
            icon.notify(message, "NEXUS")
        except Exception:
            pass  # not all platforms support tray notifications

    # ── Build & run ──
    def run(self):
        try:
            import pystray
        except ImportError:
            print("pystray not installed. Run: pip install pystray pillow")
            return

        menu = pystray.Menu(
            pystray.MenuItem("Start API server", self.start_api),
            pystray.MenuItem("Open UI", self.open_ui),
            pystray.MenuItem("Voice: push to talk", self.voice_ptt),
            pystray.MenuItem("Status", self.show_status),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit),
        )
        icon = pystray.Icon("nexus", _make_icon_image(), "NEXUS OS Bot", menu)
        print("NEXUS tray running. Look for the 'NX' icon in your system tray.")
        icon.run()


if __name__ == "__main__":
    NexusTray().run()
