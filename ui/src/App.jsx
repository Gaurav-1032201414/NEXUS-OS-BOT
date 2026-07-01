import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  getHealth, getStatus, sendChat, streamChat,
  voiceStatus, voicePushToTalk, voiceSpeak,
  Shell, waitForBackend,
} from "./api.js";

export default function App() {
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [busy, setBusy]           = useState(false);
  const [health, setHealth]       = useState(null);
  const [status, setStatus]       = useState(null);
  const [voice, setVoice]         = useState(null);
  const [connected, setConnected] = useState(false);
  const [backendBusy, setBackendBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [useStreaming, setUseStreaming] = useState(false);
  const scrollRef = useRef(null);
  const listenLoopRef = useRef(false);

const poll = useCallback(async () => {
    // Health alone determines "connected". Status/voice are best-effort and
    // must never knock the app offline if they fail or are slow.
    try {
      const h = await getHealth();
      setHealth(h);
      setConnected(true);
    } catch {
      setConnected(false);
      setHealth(null);
      setStatus(null);
      return;
    }
    try { setStatus(await getStatus()); } catch { /* keep last */ }
    try { setVoice(await voiceStatus()); } catch { /* keep last */ }
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [poll]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  function pushMessage(role, content) {
    setMessages((m) => [...m, { role, content, id: Date.now() + Math.random() }]);
  }

  // ── Backend control button ──
  async function toggleBackend() {
    setBackendBusy(true);
    if (connected) {
      const res = await Shell.stopBackend();
      pushMessage("system", res.msg);
      setConnected(false);
    } else {
      pushMessage("system", "Starting backend...");
      const res = await Shell.startBackend();
      if (!res.ok) {
        pushMessage("system", res.msg);
      } else {
        const up = await waitForBackend(15000);
        if (up) {
          setConnected(true);     // flip immediately; poll confirms details
          await poll();
          pushMessage("system", "Backend online.");
        } else {
          pushMessage("system", "Backend started but not responding yet — check Ollama is running.");
        }
      }    
    }
    setBackendBusy(false);
  }

  // ── Chat ──
  async function handleSend() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    pushMessage("user", text);
    setBusy(true);

    if (useStreaming) {
      let acc = "";
      const idx = Date.now();
      pushMessage("assistant", "");
      streamChat(text, "ui", {
        onChunk: (c) => {
          acc += c;
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", content: acc, id: idx };
            return copy;
          });
        },
        onDone: () => setBusy(false),
        onError: (e) => { pushMessage("system", `[Error] ${e}`); setBusy(false); },
      });
    } else {
      try {
        const res = await sendChat(text, "ui", true);
        pushMessage("assistant", res.reply);
      } catch (e) {
        pushMessage("system", `[Error] ${e.message}. Is the backend running?`);
      }
      setBusy(false);
    }
  }

  // ── Voice: single push-to-talk ──
  async function handlePushToTalk() {
    if (busy || !connected) return;
    setBusy(true);
    pushMessage("system", "🎙 Listening...");
    try {
      const res = await voicePushToTalk();
      if (res.ok) {
        pushMessage("user", res.transcript);
        pushMessage("assistant", res.reply);
      } else {
        pushMessage("system", res.transcript || "Didn't catch that.");
      }
    } catch (e) {
      pushMessage("system", `Voice error: ${e.message}`);
    }
    setBusy(false);
  }

  // ── Voice: continuous listen toggle ──
  async function toggleListening() {
    if (listening) {
      listenLoopRef.current = false;
      setListening(false);
      pushMessage("system", "Stopped listening.");
      return;
    }
    if (!connected) { pushMessage("system", "Start the backend first."); return; }
    listenLoopRef.current = true;
    setListening(true);
    pushMessage("system", "🎧 Continuous listening on. Speak anytime.");
    // Loop: each push_to_talk records ~6s, responds, then we go again
    while (listenLoopRef.current) {
      try {
        const res = await voicePushToTalk();
        if (!listenLoopRef.current) break;
        if (res.ok && res.transcript?.trim()) {
          pushMessage("user", res.transcript);
          pushMessage("assistant", res.reply);
        }
      } catch (e) {
        pushMessage("system", `Voice error: ${e.message}`);
        break;
      }
    }
    setListening(false);
  }

  const speechReady = voice?.stt_available && voice?.tts_available;

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <span className="logo-mark">NX</span>
          <span className="logo-text">NEX<b>US</b></span>
        </div>
        <div className="header-right">
          <button
            className={`backend-btn ${connected ? "on" : "off"}`}
            onClick={toggleBackend}
            disabled={backendBusy}
            title={Shell.available() ? "" : "Desktop app required to control the backend"}
          >
            <span className="dot" />
            {backendBusy ? "..." : connected ? "Backend on" : "Start backend"}
          </button>
        </div>
      </header>

      <div className="body">
        <aside className="sidebar">
          <Stat label="Ollama" value={health?.ollama_alive ? "Online" : "Offline"} good={health?.ollama_alive} />
          <Stat label="Model" value={status?.router?.selected_model || "—"} />
          <Stat label="Profile" value={status?.router?.profile || "—"} />
          <Stat label="Tools" value={health?.tools_loaded ?? "—"} />
          <div className="divider" />
          <Stat label="CPU" value={status ? `${Math.round(status.guard?.cpu || 0)}%` : "—"} />
          <Stat label="RAM free" value={status ? `${status.guard?.ram_avail_gb ?? "—"} GB` : "—"} />
          <div className="divider" />
          <Stat label="Speech in" value={voice?.stt_available ? "Ready" : "Off"} good={voice?.stt_available} />
          <Stat label="Speech out" value={voice?.tts_available ? "Ready" : "Off"} good={voice?.tts_available} />

          <div className="divider" />
          <button
            className={`listen-btn ${listening ? "active" : ""}`}
            onClick={toggleListening}
            disabled={!connected || !speechReady}
            title={speechReady ? "" : "Voice deps not installed on the backend"}
          >
            {listening ? "■ Stop listening" : "🎧 Start listening"}
          </button>
        </aside>

        <main className="chat">
          <div className="messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="empty">
                {connected
                  ? 'Ask NEXUS to do something — "list my home directory", "what\'s using the most memory?", "open github.com".'
                  : 'Press "Start backend" above to begin. Make sure Ollama is running.'}
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>
                <div className="msg-role">{m.role}</div>
                <div className="msg-content">{m.content || (busy ? "…" : "")}</div>
              </div>
            ))}
          </div>

          <div className="composer">
            <button className="mic" onClick={handlePushToTalk}
                    disabled={busy || !connected || !speechReady}
                    title={speechReady ? "Push to talk (one message)" : "Voice not available"}>
              🎙
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder={connected ? "Type a command..." : "Backend offline — press Start backend"}
              disabled={busy || !connected}
            />
            <button className="send" onClick={handleSend} disabled={busy || !connected}>
              {busy ? "..." : "Send"}
            </button>
          </div>
          <label className="stream-toggle">
            <input type="checkbox" checked={useStreaming}
                   onChange={(e) => setUseStreaming(e.target.checked)} />
            Stream responses (faster, but no tool actions)
          </label>
        </main>
      </div>
    </div>
  );
}

function Stat({ label, value, good }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${good === true ? "ok" : good === false ? "bad" : ""}`}>
        {value}
      </span>
    </div>
  );
}
