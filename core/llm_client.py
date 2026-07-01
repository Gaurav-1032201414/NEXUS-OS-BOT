"""
core/llm_client.py
Unified LLM interface. Talks to Ollama (local) or OpenAI (cloud fallback).
Supports both plain chat and tool/function calling.
"""
import json
import logging
import os
import requests

logger = logging.getLogger("nexus.llm")


class LLMError(Exception):
    pass


class LLMClient:
    """
    Wraps Ollama's HTTP API. The /api/chat endpoint supports tools natively
    for models that implement function calling (llama3.1, llama3.2, etc.).
    """

    def __init__(self, host: str = "http://localhost:11434", timeout: int = 120):
        self.host    = host.rstrip("/")
        self.timeout = timeout

    # ── Availability ──────────────────────────────

    def is_alive(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            logger.warning(f"list_models failed: {e}")
            return []

    # ── Chat ──────────────────────────────────────

    def chat(self, model: str, messages: list[dict],
             tools: list[dict] | None = None,
             temperature: float = 0.2) -> dict:
        """
        Send a chat request. Returns the full message dict from Ollama:
        {"role": "assistant", "content": "...", "tool_calls": [...]}
        Tool calls only appear if `tools` provided AND the model supports them.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools

        try:
            r = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("message", {"role": "assistant", "content": ""})
        except requests.exceptions.ConnectionError:
            raise LLMError(
                "Cannot reach Ollama. Is it running? Start it with: ollama serve"
            )
        except requests.exceptions.Timeout:
            raise LLMError(f"Ollama timed out after {self.timeout}s. Try a smaller model.")
        except requests.exceptions.HTTPError as e:
            # Most common: model not pulled
            body = ""
            try:
                body = r.text
            except Exception:
                pass
            if "not found" in body.lower():
                raise LLMError(
                    f"Model '{model}' is not installed. Pull it with: ollama pull {model}"
                )
            raise LLMError(f"Ollama HTTP error: {e} — {body}")
        except Exception as e:
            raise LLMError(f"Unexpected LLM error: {e}")

    def chat_stream(self, model: str, messages: list[dict],
                    temperature: float = 0.2):
        """Generator yielding content chunks as they arrive. For the WebSocket UI."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            with requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=True,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    msg = chunk.get("message", {})
                    if msg.get("content"):
                        yield msg["content"]
                    if chunk.get("done"):
                        break
        except requests.exceptions.ConnectionError:
            raise LLMError("Cannot reach Ollama. Start it with: ollama serve")
        except Exception as e:
            raise LLMError(f"Stream error: {e}")


class OpenAIClient:
    """Cloud fallback. Only used when local resources are exhausted."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model   = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict], tools=None, temperature=0.7) -> dict:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY not set; cloud fallback unavailable.")
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            payload["tools"] = tools
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json=payload, timeout=120,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]
        except Exception as e:
            raise LLMError(f"OpenAI error: {e}")
