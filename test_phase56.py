"""
test_phase56.py
Integration tests for Phase 5 (voice) and Phase 6 (tray + API voice endpoints).
Mocks audio + Ollama so it runs in any environment.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from unittest.mock import patch, MagicMock

P, F = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
res = []
def ck(n, c): res.append(c); print(f"  [{P if c else F}] {n}")

print("\n=== Phase 5: Voice module imports ===")
from voice import stt, tts, voice_loop, wake_word
ck("stt imports", hasattr(stt, "listen"))
ck("tts imports", hasattr(tts, "speak"))
ck("voice_loop imports", hasattr(voice_loop, "VoiceLoop"))
ck("wake_word imports", hasattr(wake_word, "WakeWordDetector"))

print("\n=== Phase 5: Graceful degradation (no audio hardware) ===")
ck("tts.speak returns guidance, no crash", "Install" in tts.speak("hi") or "via" in tts.speak("hi"))
ck("stt.listen returns guidance, no crash", "[" in stt.listen(1))
diag = voice_loop.diagnostics()
ck("diagnostics has both keys", "stt_available" in diag and "tts_available" in diag)

print("\n=== Phase 5: Voice tools registered in agent ===")
from core import tools
ck("speak tool registered", "speak" in tools.tool_names())
ck("voice_status tool registered", "voice_status" in tools.tool_names())
ck("speak dispatch works", isinstance(tools.dispatch("speak", {"text": "x"}), str))

print("\n=== Phase 5: VoiceLoop with mocked agent ===")
fake_agent = MagicMock()
fake_agent.chat.return_value = "Mocked reply"
loop = voice_loop.VoiceLoop(fake_agent)
events = []
loop.set_event_callback(lambda k, t="": events.append(k))
# Mock stt.listen to return a transcript, tts.speak to no-op
with patch("voice.voice_loop.stt") as mock_stt, \
     patch("voice.voice_loop.tts") as mock_tts:
    mock_stt.listen.return_value = "open my files"
    mock_tts.speak.return_value = "spoke"
    result = loop.push_to_talk()
ck("push_to_talk completes", result["ok"] is True)
ck("transcript captured", result["transcript"] == "open my files")
ck("agent was called", fake_agent.chat.called)
ck("reply returned", result["reply"] == "Mocked reply")
ck("events emitted", "listening" in events and "speaking" in events)

print("\n=== Phase 6: Tray instantiation ===")
import tray
ck("icon image generates", tray._make_icon_image().size == (64, 64))
t = tray.NexusTray()
ck("NexusTray instantiates", t is not None)
ck("has menu actions", all(hasattr(t, m) for m in ["start_api","voice_ptt","show_status","quit"]))

print("\n=== Phase 6: API voice endpoints (mocked) ===")
def fake_alive(self): return True
def fake_list(self): return ["phi3:mini"]
def fake_chat(self, model, messages, tools=None, temperature=0.7):
    return {"role": "assistant", "content": "ok"}
with patch("core.llm_client.LLMClient.is_alive", fake_alive), \
     patch("core.llm_client.LLMClient.list_models", fake_list), \
     patch("core.llm_client.LLMClient.chat", fake_chat), \
     patch("performance.model_router.ModelRouter._refresh_available", lambda s: None):
    from performance.model_router import ModelRouter
    ModelRouter.best_model = lambda self, force_refresh=False: "phi3:mini"
    from fastapi.testclient import TestClient
    from api.server import app
    client = TestClient(app); client.__enter__()
    r = client.get("/api/voice/status")
    ck("GET /api/voice/status → 200", r.status_code == 200)
    ck("voice status has stt key", "stt_available" in r.json())
    r = client.post("/api/voice/speak", json={"text": "hello"})
    ck("POST /api/voice/speak → 200", r.status_code == 200)

print("\n" + "="*40)
print(f"  RESULTS: {sum(res)}/{len(res)} passed")
print("="*40 + "\n")
sys.exit(0 if all(res) else 1)
