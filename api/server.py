"""
api/server.py
FastAPI server exposing NEXUS over REST + WebSocket.
This is the bridge the future desktop UI (Tauri/React) will talk to.

Run:  python -m api.server   (or via uvicorn)
"""
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import get_config
from core.agent import NexusAgent

logger = logging.getLogger("nexus.api")

cfg = get_config()
app = FastAPI(title="NEXUS OS Bot API", version="1.0.0")

# Allow the local desktop UI to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared agent instance
agent: NexusAgent | None = None


@app.on_event("startup")
def _startup():
    global agent
    agent = NexusAgent()
    logger.info("NEXUS agent ready")


@app.on_event("shutdown")
def _shutdown():
    if agent:
        agent.shutdown()


# ── REST models ──

class ChatRequest(BaseModel):
    message: str
    session: str = "api"
    use_tools: bool = True


class ChatResponse(BaseModel):
    reply: str


# ── REST endpoints ──

@app.get("/api/health")
def health():
    return agent.health()


@app.get("/api/system")
def system():
    from os_control import system_info
    return system_info.full_scan()

@app.get("/api/status")
def status():
    return {
        "router": agent.router.report(),
        "guard":  agent.guard.snapshot(),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply = agent.chat(req.message, session=req.session, use_tools=req.use_tools)
    return ChatResponse(reply=reply)


@app.post("/api/clear")
def clear(session: str = "api"):
    agent.memory.clear_session(session)
    return {"status": "cleared", "session": session}


# ── WebSocket for streaming chat ──

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                message = data.get("message", "")
                session = data.get("session", "ws")
            except json.JSONDecodeError:
                message, session = raw, "ws"

            # Stream chunks back to the client
            await ws.send_json({"type": "start"})
            for chunk in agent.chat_stream(message, session=session):
                await ws.send_json({"type": "chunk", "content": chunk})
            await ws.send_json({"type": "end"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await ws.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


def run():
    import uvicorn
    host = cfg.get("api.host", "127.0.0.1")
    port = cfg.get("api.port", 8765)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()


# ── Phase 5: Voice endpoints ──

_voice_loop = None

@app.get("/api/voice/status")
def voice_status():
    from voice.voice_loop import diagnostics
    return diagnostics()


@app.post("/api/voice/push_to_talk")
def voice_ptt():
    """Trigger a single record→respond→speak exchange. Blocks until done."""
    global _voice_loop
    from voice.voice_loop import VoiceLoop
    if _voice_loop is None:
        _voice_loop = VoiceLoop(agent)
    result = _voice_loop.push_to_talk()
    return result


@app.post("/api/voice/speak")
def voice_speak(payload: dict):
    from voice import tts
    return {"status": tts.speak(payload.get("text", ""))}


# ── Directory index endpoints ──

@app.get("/api/index/info")
def index_info():
    from os_control import directory_index
    return {"info": directory_index.cache_info()}


@app.post("/api/index/rebuild")
def index_rebuild():
    from os_control import directory_index
    idx = directory_index.rebuild()
    agent.memory.set_fact("directory_summary", directory_index.summarize(idx))
    return {"status": "rebuilt", "entries": idx.get("total_entries", 0)}


@app.get("/api/index/changes")
def index_changes():
    """Trigger a change check and return what's new/removed since last scan."""
    if agent and getattr(agent, "index_watcher", None):
        return agent.index_watcher.force_check()
    from os_control import directory_index
    return directory_index.refresh_if_changed()
