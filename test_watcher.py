"""Test the periodic index watcher integration."""
import sys, os, tempfile, shutil, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from unittest.mock import patch

P, F = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
res = []
def ck(n, c): res.append(c); print(f"  [{P if c else F}] {n}")

fake = tempfile.mkdtemp()
os.makedirs(f"{fake}/Documents", exist_ok=True)
open(f"{fake}/Documents/start.txt", "w").write("x")
os.environ["HOME"] = fake

from os_control import directory_index as di
di.CACHE_PATH = Path(fake) / ".nexus" / "index.json"

print("\n=== refresh_if_changed ===")
di.build_index(force=True)
r = di.refresh_if_changed()
ck("no change detected initially", r["changed"] is False)
open(f"{fake}/Documents/added.txt", "w").write("x")
r = di.refresh_if_changed()
ck("detects added file", r["changed"] and any("added.txt" in a for a in r["added"]))
r2 = di.refresh_if_changed()
ck("no change on second check", r2["changed"] is False)

print("\n=== diff function ===")
old = {"roots": {"D": {"files": ["a"], "dirs": {}}}}
new = {"roots": {"D": {"files": ["a", "b"], "dirs": {}}}}
d = di.diff(old, new)
ck("diff finds added", "D/b" in d["added"])
ck("diff no false removals", d["removed"] == [])

print("\n=== IndexWatcher ===")
from os_control.index_watcher import IndexWatcher
events = []
w = IndexWatcher(interval_seconds=30, on_change=lambda x: events.append(x))
ck("interval floored at 30", w.interval == 30)
w2 = IndexWatcher(interval_seconds=5)
ck("low interval floored to 30", w2.interval == 30)

open(f"{fake}/Documents/viaforce.txt", "w").write("x")
diff = w.force_check()
ck("force_check detects change", diff["changed"])
ck("on_change callback fired", len(events) == 1)
last = w.last_diff()
ck("last_diff returns dict", isinstance(last, dict) and "changed" in last)

print("\n=== Watcher starts/stops as thread ===")
w.start()
ck("thread running", w._thread is not None and w._thread.is_alive())
w.stop()
time.sleep(0.1)
ck("thread stopped", not w._thread.is_alive())

print("\n=== Agent wires watcher ===")
def fake_alive(self): return True
def fake_list(self): return ["phi3:mini"]
def fake_chat(self, model, messages, tools=None, temperature=0.2):
    return {"role": "assistant", "content": "ok"}
with patch("core.llm_client.LLMClient.is_alive", fake_alive), \
     patch("core.llm_client.LLMClient.list_models", fake_list), \
     patch("core.llm_client.LLMClient.chat", fake_chat), \
     patch("performance.model_router.ModelRouter._refresh_available", lambda s: None):
    from performance.model_router import ModelRouter
    ModelRouter.best_model = lambda self, force_refresh=False: "phi3:mini"
    di.CACHE_PATH = Path(fake) / ".nexus" / "index.json"
    from core.agent import NexusAgent
    agent = NexusAgent()
    ck("agent has index_watcher", getattr(agent, "index_watcher", None) is not None)
    ck("watcher thread alive", agent.index_watcher._thread.is_alive())
    # Simulate a change and confirm the agent refreshes its map
    open(f"{fake}/Documents/agentsaw.txt", "w").write("x")
    agent.index_watcher.force_check()
    summ = agent.memory.get_fact("directory_summary")
    ck("agent map refreshed on change", summ is not None)
    agent.shutdown()
    time.sleep(0.1)
    ck("watcher stopped on shutdown", not agent.index_watcher._thread.is_alive())

from core import tools
ck("recent_changes tool registered", "recent_changes" in tools.tool_names())

shutil.rmtree(fake, ignore_errors=True)
print("\n" + "="*40)
print(f"  RESULTS: {sum(res)}/{len(res)} passed")
print("="*40 + "\n")
sys.exit(0 if all(res) else 1)
