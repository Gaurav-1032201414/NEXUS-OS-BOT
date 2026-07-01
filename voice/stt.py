"""
voice/stt.py
Speech-to-text via Whisper. Lazy-loads the model (it's heavy) and records
from the default mic. Falls back with clear instructions if deps are missing.

Two engines supported:
  - faster-whisper (preferred: 4x faster, less RAM)
  - openai-whisper (reference implementation)
"""
import os
import tempfile
import logging
import wave

logger = logging.getLogger("nexus.stt")

_model = None
_engine = None   # "faster" | "openai" | None
_SAMPLE_RATE = 16000


def _load_model(size: str = "base"):
    """Load a Whisper model once, preferring faster-whisper."""
    global _model, _engine
    if _model is not None:
        return _model

    # Try faster-whisper first
    try:
        from faster_whisper import WhisperModel
        _model = WhisperModel(size, device="cpu", compute_type="int8")
        _engine = "faster"
        logger.info(f"Loaded faster-whisper '{size}'")
        return _model
    except Exception as e:
        logger.debug(f"faster-whisper unavailable: {e}")

    # Fall back to openai-whisper
    try:
        import whisper
        _model = whisper.load_model(size)
        _engine = "openai"
        logger.info(f"Loaded openai-whisper '{size}'")
        return _model
    except Exception as e:
        logger.debug(f"openai-whisper unavailable: {e}")

    _engine = None
    return None


def record(seconds: float = 5.0) -> str | None:
    """Record from the mic to a temp WAV file. Returns path or None."""
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        logger.warning("sounddevice/numpy not installed")
        return None

    try:
        logger.info(f"Recording {seconds}s...")
        audio = sd.rec(int(seconds * _SAMPLE_RATE),
                       samplerate=_SAMPLE_RATE, channels=1, dtype="int16")
        sd.wait()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return path
    except Exception as e:
        logger.warning(f"Recording failed: {e}")
        return None


def transcribe_file(wav_path: str, model_size: str = "base") -> str:
    """Transcribe an existing WAV file."""
    model = _load_model(model_size)
    if model is None:
        return ("[STT unavailable] Install Whisper:\n"
                "  pip install faster-whisper sounddevice")
    try:
        if _engine == "faster":
            segments, _ = model.transcribe(wav_path, language="en")
            return " ".join(s.text for s in segments).strip()
        else:  # openai
            result = model.transcribe(wav_path, language="en")
            return result["text"].strip()
    except Exception as e:
        return f"[Transcription error] {e}"


def listen(seconds: float = 5.0, model_size: str = "base") -> str:
    """Record from mic and transcribe in one call."""
    wav = record(seconds)
    if wav is None:
        return ("[Microphone unavailable] Install audio deps:\n"
                "  pip install sounddevice numpy\n"
                "  sudo apt install portaudio19-dev   # Linux")
    try:
        text = transcribe_file(wav, model_size)
        return text
    finally:
        try:
            os.unlink(wav)
        except Exception:
            pass


def is_available() -> bool:
    try:
        import sounddevice  # noqa
        ok_audio = True
    except ImportError:
        ok_audio = False
    has_model = False
    try:
        import faster_whisper  # noqa
        has_model = True
    except ImportError:
        try:
            import whisper  # noqa
            has_model = True
        except ImportError:
            pass
    return ok_audio and has_model
