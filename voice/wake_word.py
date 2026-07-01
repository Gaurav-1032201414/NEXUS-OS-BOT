"""
voice/wake_word.py
Wake-word detection ("Hey Nexus"). Two strategies:
  1. Porcupine (pvporcupine) — accurate, low-CPU, needs a free access key
  2. Energy-gate fallback — listens for any speech-level audio, then hands off
     to Whisper which checks if the transcript contains the wake phrase.
The fallback needs no API key and works everywhere sounddevice does.
"""
import os
import logging
import time

logger = logging.getLogger("nexus.wake")

_DEFAULT_PHRASE = "nexus"


class WakeWordDetector:
    def __init__(self, phrase: str = _DEFAULT_PHRASE, access_key: str | None = None):
        self.phrase      = phrase.lower()
        self.access_key  = access_key or os.environ.get("PORCUPINE_ACCESS_KEY")
        self._porcupine  = None
        self._mode       = self._init_porcupine() or "energy"
        logger.info(f"Wake word detector mode: {self._mode}")

    def _init_porcupine(self) -> str | None:
        if not self.access_key:
            return None
        try:
            import pvporcupine
            # Built-in keyword closest to "nexus" — use "computer" as a stand-in,
            # or supply a custom .ppn keyword file for true "Hey Nexus".
            self._porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=["computer"],
            )
            return "porcupine"
        except Exception as e:
            logger.debug(f"Porcupine init failed: {e}")
            return None

    # ── Porcupine path ──

    def _wait_porcupine(self) -> bool:
        try:
            import sounddevice as sd
            import struct
            pcm_len = self._porcupine.frame_length
            with sd.RawInputStream(samplerate=self._porcupine.sample_rate,
                                   blocksize=pcm_len, dtype="int16",
                                   channels=1) as stream:
                while True:
                    data, _ = stream.read(pcm_len)
                    pcm = struct.unpack_from("h" * pcm_len, data)
                    if self._porcupine.process(pcm) >= 0:
                        return True
        except Exception as e:
            logger.warning(f"Porcupine listen failed: {e}")
            return False

    # ── Energy-gate fallback path ──

    def _wait_energy(self) -> bool:
        """
        Listen in short windows. When audio energy crosses a threshold,
        transcribe that window and check for the wake phrase.
        """
        try:
            import sounddevice as sd
            import numpy as np
            from voice import stt
        except ImportError:
            logger.warning("Energy wake-word needs sounddevice+numpy+whisper")
            time.sleep(1)
            return False

        sr = 16000
        window = 1.5  # seconds
        threshold = 500  # int16 RMS energy

        while True:
            audio = sd.rec(int(window * sr), samplerate=sr, channels=1, dtype="int16")
            sd.wait()
            rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
            if rms < threshold:
                continue
            # Speech detected — transcribe and check phrase
            import tempfile, wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                wf.writeframes(audio.tobytes())
            text = stt.transcribe_file(path).lower()
            try:
                os.unlink(path)
            except Exception:
                pass
            if self.phrase in text:
                return True

    def wait_for_wake(self) -> bool:
        """Block until the wake word is detected. Returns True on detection."""
        if self._mode == "porcupine":
            return self._wait_porcupine()
        return self._wait_energy()

    def is_available(self) -> bool:
        try:
            import sounddevice  # noqa
            return True
        except ImportError:
            return False
