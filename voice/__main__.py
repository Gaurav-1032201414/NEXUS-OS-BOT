"""
voice/__main__.py
Standalone voice mode. Run:  python -m voice
  --once         single push-to-talk exchange
  --continuous   always-on wake-word loop (say "nexus")
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

from core.agent import NexusAgent
from voice.voice_loop import VoiceLoop, diagnostics


def main():
    print("\nNEXUS Voice — initializing...\n")
    diag = diagnostics()
    print(f"  Speech-to-text: {'available' if diag['stt_available'] else 'NOT available'}")
    print(f"  Text-to-speech: {'available' if diag['tts_available'] else 'NOT available'}")

    if not diag["stt_available"] or not diag["tts_available"]:
        print("\n  Install voice dependencies first:")
        print("    pip install faster-whisper sounddevice pyttsx3 numpy")
        print("    sudo apt install portaudio19-dev espeak-ng   # Linux\n")
        return

    agent = NexusAgent()
    loop  = VoiceLoop(agent)

    def on_event(kind, text=""):
        labels = {
            "listening": "Listening...", "transcript": f"You said: {text}",
            "thinking": "Thinking...", "reply": f"NEXUS: {text}",
            "speaking": "Speaking...", "ready": "Ready",
            "waiting_for_wake": 'Say "nexus" to activate',
        }
        if kind in labels:
            print(f"  [{labels[kind]}]")

    loop.set_event_callback(on_event)

    try:
        if "--continuous" in sys.argv:
            print('\n  Continuous mode. Say "nexus" to wake. Ctrl+C to quit.\n')
            loop.run_continuous()
        else:
            print("\n  Push-to-talk: recording 6 seconds. Speak now.\n")
            loop.push_to_talk()
    except KeyboardInterrupt:
        loop.stop()
    finally:
        agent.shutdown()
        print("\n  Voice mode ended.")


if __name__ == "__main__":
    main()
