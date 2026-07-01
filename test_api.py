"""Quick test that the FastAPI app boots and endpoints respond (mocked LLM)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from unittest.mock import patch
from fastapi.testclient import TestClient

def fake_alive(self): return True
def fake_list(self): return ["phi3:mini"]
def fake_chat(self, model, messages, tools=None, temperature=0.7):
    return {"role": "assistant", "content": "Hello from NEXUS (mocked)."}

with patch("core.llm_client.LLMClient.is_alive", fake_alive), \
     patch("core.llm_client.LLMClient.list_models", fake_list), \
     patch("core.llm_client.LLMClient.chat", fake_chat), \
     patch("performance.model_router.ModelRouter._refresh_available", lambda s: None):
    from performance.model_router import ModelRouter
    ModelRouter.best_model = lambda self, force_refresh=False: "phi3:mini"
    from api.server import app

    client = TestClient(app)
    client.__enter__()  # trigger startup event
    P, F = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
    res = []
    def ck(n, c): res.append(c); print(f"  [{P if c else F}] {n}")

    r = client.get("/api/health")
    ck("GET /api/health → 200", r.status_code == 200)
    ck("health has tools_loaded", "tools_loaded" in r.json())

    r = client.get("/api/system")
    ck("GET /api/system → 200", r.status_code == 200)
    ck("system has hardware", "hardware" in r.json())

    r = client.get("/api/status")
    ck("GET /api/status → 200", r.status_code == 200)

    r = client.post("/api/chat", json={"message": "hi", "use_tools": False})
    ck("POST /api/chat → 200", r.status_code == 200)
    ck("chat returns reply", "NEXUS" in r.json()["reply"])

    print(f"\n  API: {sum(res)}/{len(res)} passed\n")
    sys.exit(0 if all(res) else 1)
