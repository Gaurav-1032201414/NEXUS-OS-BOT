"""
voice/tts.py
Text-to-speech. Tries multiple backends in order of quality:
  1. Piper (best, local neural TTS)
  2. pyttsx3 (cross-platform, offline, robotic but reliable)
  3. espeak-ng / say / PowerShell (OS built-ins)
All return a status string. speak() never raises.
"""
import os
import shutil
import subprocess
import tempfile
import logging
import platform

logger = logging.getLogger("nexus.tts")

_PIPER_BIN   = os.path.expanduser("~/.local/bin/piper/piper")
_PIPER_MODEL = os.path.expanduser("~/.nexus/voices/en_US-lessac-medium.onnx")

_pyttsx3_engine = None


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _try_piper(text: str) -> bool:
    if not (os.path.exists(_PIPER_BIN) and os.path.exists(_PIPER_MODEL)):
        return False
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav = f.name
        subprocess.run(
            [_PIPER_BIN, "--model", _PIPER_MODEL, "--output_file", wav],
            input=text.encode(), check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
        )
        _play_wav(wav)
        os.unlink(wav)
        return True
    except Exception as e:
        logger.debug(f"Piper failed: {e}")
        return False


def _try_pyttsx3(text: str) -> bool:
    global _pyttsx3_engine
    try:
        if _pyttsx3_engine is None:
            import pyttsx3
            _pyttsx3_engine = pyttsx3.init()
            _pyttsx3_engine.setProperty("rate", 175)
        _pyttsx3_engine.say(text)
        _pyttsx3_engine.runAndWait()
        return True
    except Exception as e:
        logger.debug(f"pyttsx3 failed: {e}")
        return False


def _try_os_native(text: str) -> bool:
    system = platform.system()
    try:
        if system == "Darwin" and _have("say"):
            subprocess.run(["say", text], timeout=30)
            return True
        if system == "Linux" and _have("espeak-ng"):
            subprocess.run(["espeak-ng", text], timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if system == "Linux" and _have("espeak"):
            subprocess.run(["espeak", text], timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if system == "Windows":
            ps = (f'Add-Type -AssemblyName System.Speech; '
                  f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")')
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=30)
            return True
    except Exception as e:
        logger.debug(f"OS-native TTS failed: {e}")
    return False


def _play_wav(path: str):
    """Play a WAV file using whatever player is available."""
    for player in (["aplay", path], ["paplay", path],
                   ["afplay", path], ["ffplay", "-nodisp", "-autoexit", path]):
        if _have(player[0]):
            subprocess.run(player, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30)
            return


def speak(text: str) -> str:
    """Speak text aloud. Returns a status string; never raises."""
    if not text or not text.strip():
        return "Nothing to speak"
    text = text.strip()

    if _try_piper(text):
        return f"Spoke ({len(text)} chars) via Piper"
    if _try_pyttsx3(text):
        return f"Spoke ({len(text)} chars) via pyttsx3"
    if _try_os_native(text):
        return f"Spoke ({len(text)} chars) via OS TTS"
    return ("No TTS backend available. Install one:\n"
            "  pip install pyttsx3   (cross-platform)\n"
            "  or on Linux: sudo apt install espeak-ng")


def is_available() -> bool:
    return (
        (os.path.exists(_PIPER_BIN) and os.path.exists(_PIPER_MODEL))
        or _have("espeak-ng") or _have("espeak") or _have("say")
        or platform.system() == "Windows"
    )
