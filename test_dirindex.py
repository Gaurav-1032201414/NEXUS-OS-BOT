"""Test directory index integration + anti-hallucination prompt."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from unittest.mock import patch

P, F = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
res = []
def ck(n, c): res.append(c); print(f"  [{P if c else F}] {n}")

# Build a fake home with known content
import tempfile, shutil
fake = tempfile.mkdtemp()
os.makedirs(f"{fake}/Documents/Work", exist_ok=True)
os.makedirs(f"{fake}/Downloads", exist_ok=True)
open(f"{fake}/Documents/budget.xlsx", "w").write("x")
open(f"{fake}/Downloads/setup.exe", "w").write("x")

print("\n=== Directory index core ===")
with patch.dict(os.environ, {"HOME": fake}):
    # Point cache into the fake home too
    from os_control import directory_index as di
    di.CACHE_PATH = Path(fake) / ".nexus" / "directory_index.json"

    idx = di.build_index(force=True)
    ck("index built with entries", idx["total_entries"] >= 3)
    ck("cache file created", di.CACHE_PATH.exists())

    # Second call should load from cache (not rescan) — same object shape
    idx2 = di.build_index(force=False)
    ck("cache reload works", idx2["total_entries"] == idx["total_entries"])

    summ = di.summarize(idx)
    ck("summary lists Documents", "Documents" in summ)
    ck("summary lists Downloads", "Downloads" in summ)

    found = di.find(idx, "budget")
    ck("search finds budget.xlsx", any("budget" in m for m in found))

    found_none = di.find(idx, "zzznotreal")
    ck("search returns empty for missing", found_none == [])

print("\n=== Tools registered ===")
from core import tools
ck("search_index tool", "search_index" in tools.tool_names())
ck("rebuild_index tool", "rebuild_index" in tools.tool_names())
ck("index_info tool", "index_info" in tools.tool_names())
ck("total tools >= 43", len(tools.tool_names()) >= 43)

print("\n=== Anti-hallucination prompt ===")
def fake_alive(self): return True
def fake_list(self): return ["phi3:mini"]
def fake_chat(self, model, messages, tools=None, temperature=0.2):
    # capture temperature to verify it's low
    fake_chat.temp = temperature
    return {"role": "assistant", "content": "ok"}
with patch("core.llm_client.LLMClient.is_alive", fake_alive), \
     patch("core.llm_client.LLMClient.list_models", fake_list), \
     patch("core.llm_client.LLMClient.chat", fake_chat), \
     patch("performance.model_router.ModelRouter._refresh_available", lambda s: None), \
     patch.dict(os.environ, {"HOME": fake}):
    from performance.model_router import ModelRouter
    ModelRouter.best_model = lambda self, force_refresh=False: "phi3:mini"
    di.CACHE_PATH = Path(fake) / ".nexus" / "directory_index.json"
    from core.agent import NexusAgent
    agent = NexusAgent()
    prompt = agent._system_prompt()
    ck("prompt contains directory map", "DIRECTORY STRUCTURE" in prompt)
    ck("prompt has anti-guess rule", "NEVER invent" in prompt)
    ck("prompt forbids fabrication", "fabricat" in prompt.lower())
    ck("directory summary cached as fact", agent.memory.get_fact("directory_summary") is not None)
    agent.chat("hi", session="t")
    ck("temperature is low (0.2)", getattr(fake_chat, "temp", 1.0) == 0.2)
    agent.shutdown()

shutil.rmtree(fake, ignore_errors=True)
print("\n" + "="*40)
print(f"  RESULTS: {sum(res)}/{len(res)} passed")
print("="*40 + "\n")
sys.exit(0 if all(res) else 1)
