// src/api.js — client for the NEXUS backend + Tauri shell commands
const BASE = "http://127.0.0.1:8765";
const WS   = "ws://127.0.0.1:8765/ws";

// ── Tauri bridge ───────────────────────────────────────────
// In Tauri 2.0 the proper way to call Rust commands is to import `invoke`
// from the @tauri-apps/api package. We also support the injected global
// (window.__TAURI__) as a fallback when withGlobalTauri is enabled.
// In a plain browser neither exists, so the buttons degrade gracefully.

let _invokeFn = null;       // resolved invoke() function
let _invokeReady = null;    // promise that resolves once we've tried to load it

async function resolveInvoke() {
  if (_invokeFn) return _invokeFn;
  if (_invokeReady) return _invokeReady;

  _invokeReady = (async () => {
    // 1. Try the npm package import (primary, works in Tauri 2.0)
    try {
      const mod = await import("@tauri-apps/api/core");
      if (mod && typeof mod.invoke === "function") {
        _invokeFn = mod.invoke;
        return _invokeFn;
      }
    } catch (_) { /* not bundled or not in Tauri */ }

    // 2. Try the injected global (withGlobalTauri = true)
    if (typeof window !== "undefined" && window.__TAURI__) {
      const g = window.__TAURI__;
      if (g.core && typeof g.core.invoke === "function") {
        _invokeFn = g.core.invoke; return _invokeFn;
      }
      if (typeof g.invoke === "function") {     // older shape
        _invokeFn = g.invoke; return _invokeFn;
      }
    }

    _invokeFn = null;
    return null;
  })();

  return _invokeReady;
}

function inTauri() {
  // Best-effort synchronous hint: the global is present, or the protocol is tauri://
  if (typeof window === "undefined") return false;
  if (window.__TAURI__ || window.__TAURI_INTERNALS__) return true;
  if (typeof window.location !== "undefined" &&
      (window.location.protocol === "tauri:" || window.location.protocol === "https:" &&
       window.location.hostname === "tauri.localhost")) return true;
  return false;
}

async function tauriInvoke(cmd, args = {}) {
  const invoke = await resolveInvoke();
  if (!invoke) throw new Error("not-tauri");
  return invoke(cmd, args);
}

export const Shell = {
  available: inTauri,
  async startBackend() {
    try { return { ok: true, msg: await tauriInvoke("start_backend") }; }
    catch (e) {
      if (e.message === "not-tauri")
        return { ok: false, msg: "Tauri bridge not detected. Rebuild the app (npm install in ui/, then npm run tauri dev). Or start the backend manually: python -m api.server" };
      return { ok: false, msg: String(e) };
    }
  },
  async stopBackend() {
    try { return { ok: true, msg: await tauriInvoke("stop_backend") }; }
    catch (e) { return { ok: false, msg: String(e) }; }
  },
  async backendRunning() {
    try { return await tauriInvoke("backend_running"); }
    catch { return false; }
  },
};

// ── Backend REST/WS calls ──────────────────────────────────

async function safeFetch(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getHealth()  { return safeFetch(`${BASE}/api/health`); }
export async function getSystem()  { return safeFetch(`${BASE}/api/system`); }
export async function getStatus()  { return safeFetch(`${BASE}/api/status`); }
export async function voiceStatus(){ return safeFetch(`${BASE}/api/voice/status`); }

export async function sendChat(message, session = "ui", useTools = true) {
  return safeFetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session, use_tools: useTools }),
  });
}

export async function voicePushToTalk() {
  return safeFetch(`${BASE}/api/voice/push_to_talk`, { method: "POST" });
}

export async function voiceSpeak(text) {
  return safeFetch(`${BASE}/api/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

// Streaming chat over WebSocket
export function streamChat(message, session, { onStart, onChunk, onDone, onError }) {
  let ws;
  try { ws = new WebSocket(WS); }
  catch (e) { onError?.("Cannot open WebSocket"); return null; }
  ws.onopen = () => ws.send(JSON.stringify({ message, session }));
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "start") onStart?.();
    else if (data.type === "chunk") onChunk?.(data.content);
    else if (data.type === "end") { onDone?.(); ws.close(); }
    else if (data.type === "error") { onError?.(data.content); ws.close(); }
  };
  ws.onerror = () => onError?.("WebSocket connection failed");
  return ws;
}

// Poll the backend until it responds or times out (used after pressing Start)
export async function waitForBackend(timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try { await getHealth(); return true; }
    catch { await new Promise((r) => setTimeout(r, 800)); }
  }
  return false;
}
