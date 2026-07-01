"""
core/agent.py
The NEXUS agent. Orchestrates: system scan → model selection → chat with tools →
tool execution loop → memory persistence.

This is the brain. It runs an agentic loop: the LLM may call tools, we execute
them, feed results back, and let it continue until it produces a final answer.
"""
import json
import logging

from core.config import get_config
from core.memory import Memory
from core.llm_client import LLMClient, OpenAIClient, LLMError
from core import tools
from performance.model_router import ModelRouter, PROFILES
from performance.resource_guard import ResourceGuard
from performance import hardware_probe
from os_control import system_info

logger = logging.getLogger("nexus.agent")

MAX_TOOL_ITERATIONS = 6   # safety cap on the tool-calling loop


class NexusAgent:
    def __init__(self, config=None):
        self.cfg     = config or get_config()
        self.memory  = Memory(
            db_path=self.cfg.get("memory.db_path", "~/.nexus/memory.db"),
            max_turns=self.cfg.get("memory.max_history_turns", 20),
        )
        self.llm     = LLMClient(
            host=self.cfg.get("ollama.host", "http://localhost:11434"),
            timeout=self.cfg.get("ollama.timeout", 120),
        )
        self.openai  = OpenAIClient(model=self.cfg.get("openai.model", "gpt-4o-mini"))
        self.router  = ModelRouter(cache_ttl=self.cfg.get("performance.check_interval_seconds", 30))
        self.guard   = ResourceGuard(
            cpu_high=self.cfg.get("performance.cpu_high_threshold", 85),
            ram_min_gb=self.cfg.get("performance.ram_minimum_gb", 1.5),
        )
        self.guard.start()

        # One-time system scan, cached as a fact
        self._scan_and_cache()

        # Background watcher: periodically rescans and refreshes the cached map
        # only when files/folders actually change.
        self._start_index_watcher()

    def _start_index_watcher(self):
        try:
            from os_control.index_watcher import IndexWatcher
            interval = self.cfg.get("directory_index.scan_interval_seconds", 300)
            self.index_watcher = IndexWatcher(
                interval_seconds=interval,
                on_change=self._on_directory_change,
            )
            self.index_watcher.start()
        except Exception as e:
            logger.warning(f"Could not start index watcher: {e}")
            self.index_watcher = None

    def _on_directory_change(self, result: dict):
        """Called by the watcher when the filesystem changes — refresh the prompt map."""
        try:
            from os_control import directory_index
            self.memory.set_fact(
                "directory_summary",
                directory_index.summarize(result["index"]),
            )
            logger.info(
                f"Agent directory map refreshed (+{len(result['added'])} "
                f"-{len(result['removed'])})"
            )
        except Exception as e:
            logger.warning(f"Failed to refresh directory map: {e}")

    def _scan_and_cache(self):
        try:
            summary = system_info.summary_text()
            self.memory.set_fact("system_summary", summary)
            self.memory.set_fact("hardware", hardware_probe.probe())
            logger.info(f"System scanned: {summary}")
        except Exception as e:
            logger.warning(f"System scan failed: {e}")

        # Directory index: scan once, cache to disk. Loads instantly next time.
        try:
            from os_control import directory_index
            idx = directory_index.build_index(force=False)  # uses cache if present
            self.memory.set_fact("directory_summary", directory_index.summarize(idx))
            logger.info(f"Directory index ready: {idx.get('total_entries', 0)} entries")
        except Exception as e:
            logger.warning(f"Directory index failed: {e}")

    # ──────────────────────────────────────────────
    # System prompt
    # ──────────────────────────────────────────────

    def _system_prompt(self) -> str:
        summary   = self.memory.get_fact("system_summary", "Unknown system")
        dir_map   = self.memory.get_fact("directory_summary", "Directory index unavailable.")
        model     = self.router.best_model()
        return (
            "You are NEXUS, an OS-level AI assistant with real control over this computer.\n\n"
            f"SYSTEM: {summary}\n"
            f"ACTIVE MODEL: {model}\n\n"
            "KNOWN DIRECTORY STRUCTURE (cached snapshot of the user's home):\n"
            f"{dir_map}\n\n"
            "CRITICAL RULES — follow these exactly:\n"
            "1. NEVER invent or guess file names, paths, directory contents, process "
            "names, or any system state. If you don't have the information, CALL A TOOL "
            "to get it. Guessing is a failure.\n"
            "2. The directory snapshot above may be incomplete or out of date. To answer "
            "questions about actual current contents, use the 'list_dir' or 'search_index' "
            "or 'search_files' tools — do not rely on memory.\n"
            "3. When the user asks you to DO something (open, create, delete, list, find, "
            "launch), CALL the matching tool. Do not describe what you would do — do it.\n"
            "4. After a tool returns, report ONLY what the tool actually returned. Do not "
            "embellish or add details the tool did not provide.\n"
            "5. If a tool returns an error or empty result, say so plainly. Do not pretend "
            "it succeeded.\n"
            "6. For destructive actions (delete, kill process), state exactly what will be "
            "affected before doing it.\n"
            "7. If you genuinely cannot do something or lack a tool for it, say so directly "
            "rather than fabricating a result.\n\n"
            "Be concise and factual. Accuracy matters more than sounding helpful."
        )

    # ──────────────────────────────────────────────
    # Health
    # ──────────────────────────────────────────────

    def health(self) -> dict:
        return {
            "ollama_alive":   self.llm.is_alive(),
            "available_models": self.llm.list_models(),
            "router":         self.router.report(),
            "guard":          self.guard.snapshot(),
            "openai_configured": self.openai.is_configured(),
            "tools_loaded":   len(tools.tool_names()),
        }

    # ──────────────────────────────────────────────
    # Main chat entrypoint (non-streaming, with tools)
    # ──────────────────────────────────────────────

    def chat(self, user_input: str, session: str = "default", use_tools: bool = True) -> str:
        history = self.memory.recent_turns(session=session)
        messages = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        model = self.router.best_model()
        tool_schemas = tools.all_schemas() if use_tools else None

        try:
            final = self._run_loop(model, messages, tool_schemas)
        except LLMError as e:
            return f"[LLM error] {e}"
        except Exception as e:
            logger.exception("Agent chat crashed")
            return f"[Internal error] {e}"

        self.memory.save_exchange(user_input, final, session=session)
        return final

    def _run_loop(self, model, messages, tool_schemas) -> str:
        """
        Agentic loop. Repeatedly call the model; if it requests tool calls,
        execute them, append results, and continue. Stop when it returns plain text.
        """
        for iteration in range(MAX_TOOL_ITERATIONS):
            msg = self.llm.chat(model, messages, tools=tool_schemas)

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                # Plain answer — we're done
                return msg.get("content", "").strip() or "(no response)"

            # Record the assistant's tool-call message
            messages.append({
                "role": "assistant",
                "content": msg.get("content", ""),
                "tool_calls": tool_calls,
            })

            # Execute each requested tool
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}

                result = tools.dispatch(name, args)
                messages.append({
                    "role": "tool",
                    "content": result,
                    "name": name,
                })

        # Hit the iteration cap — ask for a final summary without tools
        msg = self.llm.chat(model, messages, tools=None)
        return msg.get("content", "").strip() or "(stopped after max tool iterations)"

    # ──────────────────────────────────────────────
    # Streaming chat (no tools) — for the WebSocket UI
    # ──────────────────────────────────────────────

    def chat_stream(self, user_input: str, session: str = "default"):
        history = self.memory.recent_turns(session=session)
        messages = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        model = self.router.best_model()
        collected = []
        try:
            for chunk in self.llm.chat_stream(model, messages):
                collected.append(chunk)
                yield chunk
        except LLMError as e:
            yield f"[LLM error] {e}"
            return

        self.memory.save_exchange(user_input, "".join(collected), session=session)

    def shutdown(self):
        if getattr(self, "index_watcher", None):
            self.index_watcher.stop()
        self.guard.stop()
        self.memory.close()
