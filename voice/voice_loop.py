"""
voice/voice_loop.py
Ties STT + agent + TTS into a conversational loop.
Two modes:
  - push_to_talk(): record once, respond once (good for testing / hotkey)
  - run_continuous(): wake word → listen → respond → repeat (always-on assistant)
Designed to run in a background thread so the tray/UI stays responsive.
"""
import logging
import threading
import time

from voice import stt, tts
from voice.wake_word import WakeWordDetector

logger = logging.getLogger("nexus.voiceloop")


class VoiceLoop:
    def __init__(self, agent, wake_phrase: str = "nexus",
                 listen_seconds: float = 6.0, model_size: str = "base"):
        self.agent          = agent
        self.wake_phrase    = wake_phrase
        self.listen_seconds = listen_seconds
        self.model_size     = model_size
        self._running       = False
        self._thread        = None
        self._on_event      = None   # optional callback(event_type, text)

    def set_event_callback(self, fn):
        """fn(event_type:str, text:str) — for UI to show state/transcripts."""
        self._on_event = fn

    def _emit(self, event_type: str, text: str = ""):
        logger.info(f"[voice:{event_type}] {text}")
        if self._on_event:
            try:
                self._on_event(event_type, text)
            except Exception:
                pass

    # ── Single exchange ──

    def push_to_talk(self) -> dict:
        """Record once, get the agent reply, speak it. Returns a result dict."""
        self._emit("listening")
        transcript = stt.listen(self.listen_seconds, self.model_size)
        if transcript.startswith("[") or not transcript.strip():
            self._emit("error", transcript)
            return {"ok": False, "transcript": transcript, "reply": None}

        self._emit("transcript", transcript)
        self._emit("thinking")
        reply = self.agent.chat(transcript, session="voice")
        self._emit("reply", reply)

        self._emit("speaking")
        tts.speak(reply)
        self._emit("idle")
        return {"ok": True, "transcript": transcript, "reply": reply}

    # ── Continuous mode ──

    def run_continuous(self):
        """Blocking loop: wake word → listen → respond. Runs until stop()."""
        if not stt.is_available():
            self._emit("error", "Speech-to-text not available. Install: pip install faster-whisper sounddevice")
            return
        if not tts.is_available():
            self._emit("error", "Text-to-speech not available. Install: pip install pyttsx3")
            return

        detector = WakeWordDetector(self.wake_phrase)
        self._running = True
        tts.speak("Nexus is ready.")
        self._emit("ready")

        while self._running:
            self._emit("waiting_for_wake", self.wake_phrase)
            detected = detector.wait_for_wake()
            if not self._running:
                break
            if detected:
                tts.speak("Yes?")
                self.push_to_talk()

    def start_background(self):
        """Run the continuous loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run_continuous, daemon=True,
                                        name="VoiceLoop")
        self._thread.start()

    def stop(self):
        self._running = False
        self._emit("stopped")


def diagnostics() -> dict:
    """Report which voice capabilities are available on this machine."""
    return {
        "stt_available": stt.is_available(),
        "tts_available": tts.is_available(),
    }
