# NEXUS OS Bot

A cross-platform, OS-native AI assistant. Runs locally with Ollama, understands
your system, controls files/processes/browser/screen, talks and listens.

## All six phases implemented

| Phase | What it does | Key files |
|-------|--------------|-----------|
| 1 — Core Agent | Ollama agent, SQLite memory, system scan, agentic tool loop | `core/` |
| 2 — OS Control | files, processes, screen, clipboard, windows, volume… (31 tools) | `os_control/` |
| 3 — Browser | Playwright automation, web search (7 tools) | `browser/` |
| 4 — Adaptive Perf | live CPU/RAM/GPU probing, model routing, resource guard | `performance/` |
| 5 — Voice | Whisper STT, Piper/pyttsx3 TTS, wake word, voice loop (2 tools) | `voice/` |
| 6 — Desktop | system tray + Tauri/React desktop app over WebSocket | `tray.py`, `ui/` |

**40 agent tools. 44 automated tests passing.**

## Install (Linux)

```bash
bash install_linux.sh        # Phases 1-4: deps, Ollama, a model
bash install_voice_ui.sh     # Phases 5-6: voice + Tauri/Node/Rust
source .venv/bin/activate
```

## Run

```bash
python main.py                      # interactive CLI (text)
python -m voice                     # voice: push-to-talk
python -m voice --continuous        # voice: always-on, say "nexus"
python -m api.server                # REST + WebSocket backend on :8765
python tray.py                      # system tray icon
cd ui && npm run tauri dev          # desktop app (needs backend running)
cd ui && npm run tauri build        # build .deb / .AppImage / .exe / .dmg
```

## How voice works (Phase 5)

`voice/` has four pieces, each degrading gracefully if deps are missing:
- `stt.py` — records mic (sounddevice) → transcribes (faster-whisper / openai-whisper)
- `tts.py` — speaks via Piper (best) → pyttsx3 → espeak-ng / say / PowerShell
- `wake_word.py` — Porcupine if you have a key, else an energy-gate + Whisper fallback
- `voice_loop.py` — wires STT → agent → TTS; `push_to_talk()` or `run_continuous()`

The agent also has `speak` and `voice_status` tools, so it can talk back on its own.

## How the desktop app works (Phase 6)

`ui/` is a Tauri (Rust) shell wrapping a React frontend (`src/App.jsx`). The Rust
`main.rs` spawns the Python backend on launch and kills it on close. The React app
talks to the FastAPI backend over REST + WebSocket (`src/api.js`): live system stats
in the sidebar, streaming chat, a mic button for push-to-talk. One codebase builds
native installers for all three OSes.

For an instant cross-platform UI without the Tauri toolchain, `tray.py` (pystray)
gives you a system-tray menu to start the API, trigger voice, and check status.

## Cross-platform

The agent never branches on OS. `os_control/platform_layer/` has `linux.py`,
`macos.py`, `windows.py` with identical function names; the right one loads at
runtime. Voice and tray use the same pattern (multiple backends, best-available wins).

## Tests

```bash
python test_harness.py     # 16 — tools, file ops, agentic loop, memory
python test_api.py         #  7 — REST endpoints
python test_phase56.py     # 21 — voice modules, voice loop, tray, voice API
```

## Project layout

```
nexus-os-bot/
├── core/            agent, memory, llm_client, tools, config
├── os_control/      file/process/screen/clipboard + platform_layer/{linux,macos,windows}
├── browser/         Playwright browser agent
├── performance/     hardware_probe, model_router, resource_guard
├── voice/           stt, tts, wake_word, voice_loop  (Phase 5)
├── api/             FastAPI REST + WebSocket
├── ui/              Tauri + React desktop app        (Phase 6)
│   ├── src/         App.jsx, api.js, styles.css
│   └── src-tauri/   main.rs, tauri.conf.json, Cargo.toml
├── tray.py          system tray (Phase 6 quick win)
├── main.py          CLI entrypoint
└── config.json
```


## Directory awareness (anti-hallucination)

NEXUS scans your home directory once on first launch and caches a compact map to
`~/.nexus/directory_index.json`. Later launches load the cache instantly.

A background watcher (`os_control/index_watcher.py`) rescans every 5 minutes
(configurable via `directory_index.scan_interval_seconds` in `config.json`) and
updates the cache **only when files or folders actually change** — added or removed
items are detected by diffing against the cache, so unchanged scans cost nothing.
When a change is found, the agent's directory map is refreshed automatically.

Relevant tools: `search_index`, `rebuild_index`, `index_info`, `recent_changes`.
CLI: `/index` (show cache info), `/reindex` (force rebuild).
API: `GET /api/index/info`, `POST /api/index/rebuild`, `GET /api/index/changes`.

To reduce hallucination further, the agent runs at temperature 0.2 and its system
prompt forbids inventing file names or system state — it must call a tool instead.


## One-click controls (desktop app)

The desktop app now has buttons — no terminal commands needed:

- **Start backend / Backend on** (top-right): the Tauri shell finds your project's
  `.venv` Python and launches `api.server` for you, then waits for it to come online.
  Click again to stop it. The backend also auto-starts when the app launches.
- **🎙 mic button** (next to the input): one push-to-talk message — records, transcribes,
  responds, speaks.
- **🎧 Start listening** (sidebar): continuous voice mode — keeps listening and
  responding until you press Stop.

Buttons that depend on the backend (voice, chat) stay disabled until it's online,
and voice buttons require the voice deps (`install_voice_ui.sh`) on the backend.
The backend control button only works in the packaged desktop app (it needs OS
process access); in a plain browser it will tell you to use the app.


## Requirements & install

One command installs everything into a `.venv`:

```bash
bash setup.sh                 # backend + frontend + voice (Linux/macOS)
bash setup.sh --no-voice      # skip heavy voice deps
bash setup.sh --backend-only  # backend only, no Node needed
```

Windows:
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

### What the requirement files contain

| File | Purpose | Install |
|------|---------|---------|
| `requirements.txt` | Core: agent, OS control, browser, API, tray (22 pkgs) | `pip install -r requirements.txt` |
| `requirements-voice.txt` | Phase 5 voice: faster-whisper, sounddevice, pyttsx3 | `pip install -r requirements-voice.txt` |
| `requirements-dev.txt` | Test-suite deps (httpx) | `pip install -r requirements-dev.txt` |

Frontend deps live in `ui/package.json` (`npm install` in `ui/`).

Notes:
- The core file is intentionally lean and was verified by a clean-venv install +
  full test run (56 tests green) — every module imports with just core deps.
- Voice uses **faster-whisper** by default (no torch/CUDA). `openai-whisper` is an
  optional fallback (commented out) because it pulls in multi-GB torch.
- After install, run `python -m playwright install chromium` if you skipped it.
- Linux voice also needs: `sudo apt install portaudio19-dev espeak-ng ffmpeg`.


## Building installers

Build native desktop installers with one command:

```bash
bash build.sh                  # build for current OS (.deb/.AppImage on Linux, .dmg on Mac)
bash build.sh --debug          # faster debug build
bash build.sh --backend        # also bundle the Python backend (no Python needed on target)
bash build.sh --frontend-only  # just compile the web frontend to ui/dist/
bash build.sh --clean          # wipe old artifacts first
```

Windows:
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
powershell -ExecutionPolicy Bypass -File build.ps1 -Backend
```

The script first checks for Node, npm, Rust/cargo (and webkit2gtk on Linux) and
prints the exact install command for anything missing before aborting. Output
installers land in `ui/src-tauri/target/release/bundle/`.

**Bundling the backend** (`--backend`): runs PyInstaller against `backend_entry.py`
to produce a standalone `nexus-backend` executable, so end users don't need Python
installed. Verified to boot and serve the API with no interpreter present.

### Cross-platform builds via CI

You can only build a `.dmg` on macOS and a `.exe` on Windows. To produce all three
without owning those machines, push a version tag — `.github/workflows/build.yml`
builds Linux, Windows, and macOS installers in parallel on GitHub's runners and
uploads them as artifacts:

```bash
git tag v1.0.0 && git push origin v1.0.0
```


### Troubleshooting: "Run the desktop app to start the backend"

This means the Tauri JS bridge wasn't detected. Fix:
1. `cd ui && npm install` — installs `@tauri-apps/api` (the button needs it).
2. Rebuild: `npm run tauri dev` (not `npm run dev`, which is browser-only).
3. The config now has `withGlobalTauri: true`, so the bridge works even without
   the npm package once rebuilt.

If the backend still won't start, set an explicit path before launching:
`export NEXUS_PROJECT_ROOT=/full/path/to/NexusOS-Bot` — or just start it manually
in a terminal: `source .venv/bin/activate && python -m api.server`.
