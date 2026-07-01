"""
test_harness.py
End-to-end test that mocks the Ollama HTTP layer so we can verify:
  - system scan
  - tool registry & dispatch
  - the agentic tool-calling loop
  - memory persistence
WITHOUT needing a real model installed. This proves the plumbing is correct.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
from unittest.mock import patch

from core import tools
from os_control import file_ops, system_info


PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []

def check(name, condition):
    results.append(condition)
    print(f"  [{PASS if condition else FAIL}] {name}")


print("\n=== 1. System info ===")
summary = system_info.summary_text()
check("summary_text returns non-empty", len(summary) > 20)
print(f"      {summary[:80]}...")

scan = system_info.full_scan()
check("full_scan has hardware", "hardware" in scan)
check("full_scan has os", "os" in scan)


print("\n=== 2. Tool registry ===")
check("registry has 25+ tools", len(tools.tool_names()) >= 25)
check("all_schemas returns list", isinstance(tools.all_schemas(), list))
schema0 = tools.all_schemas()[0]
check("schema has function.name", "name" in schema0["function"])


print("\n=== 3. File ops via dispatch ===")
test_path = "/tmp/nexus_test_file.txt"
r = tools.dispatch("create_file", {"path": test_path, "content": "hello nexus"})
check("create_file works", "Created" in r)
r = tools.dispatch("read_file", {"path": test_path})
check("read_file returns content", "hello nexus" in r)
r = tools.dispatch("file_info", {"path": test_path})
check("file_info works", "Size" in r)
r = tools.dispatch("delete_file", {"path": test_path})
check("delete_file works", "Deleted" in r)


print("\n=== 4. Unknown tool handling ===")
r = tools.dispatch("nonexistent_tool", {})
check("unknown tool handled gracefully", "Unknown tool" in r)


print("\n=== 5. Tool with bad args ===")
r = tools.dispatch("create_file", {})  # missing required 'path'
check("missing-arg handled gracefully", "error" in r.lower() or "argument" in r.lower())


print("\n=== 6. Agentic loop (mocked Ollama) ===")
# Simulate a model that: 1) calls system_info tool, 2) returns final answer
call_count = {"n": 0}

def fake_chat(self, model, messages, tools=None, temperature=0.7):
    call_count["n"] += 1
    if call_count["n"] == 1 and tools:
        # First call: request the system_info tool
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "function": {"name": "system_info", "arguments": {}}
            }]
        }
    # Second call: produce a final answer using the tool result
    last_tool = next((m for m in reversed(messages) if m.get("role") == "tool"), None)
    return {
        "role": "assistant",
        "content": f"Based on the system scan, here's your info."
    }

def fake_alive(self):
    return True

def fake_list_models(self):
    return ["phi3:mini"]

with patch("core.llm_client.LLMClient.chat", fake_chat), \
     patch("core.llm_client.LLMClient.is_alive", fake_alive), \
     patch("core.llm_client.LLMClient.list_models", fake_list_models), \
     patch("performance.model_router.ModelRouter._refresh_available", lambda s: None):
    from core.agent import NexusAgent
    from performance.model_router import ModelRouter
    # Force router to return a known model
    ModelRouter.best_model = lambda self, force_refresh=False: "phi3:mini"

    agent = NexusAgent()
    agent.memory.clear_session("test")  # isolate from prior runs
    reply = agent.chat("what system am I on?", session="test")
    check("agent completes tool loop", "system scan" in reply.lower() or "info" in reply.lower())
    check("tool was actually called (2 LLM calls)", call_count["n"] == 2)

    # Memory check
    history = agent.memory.recent_turns(session="test")
    check("exchange saved to memory", len(history) == 2)
    check("user message persisted", history[0]["content"] == "what system am I on?")

    agent.shutdown()


print("\n" + "="*40)
total, passed = len(results), sum(results)
print(f"  RESULTS: {passed}/{total} passed")
print("="*40 + "\n")
sys.exit(0 if passed == total else 1)
