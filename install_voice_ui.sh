#!/usr/bin/env bash
# NEXUS — Phase 5 (voice) + Phase 6 (desktop UI) installer
# Run after install_linux.sh, from the project root.
set -e

echo "==> NEXUS Voice + UI setup"
source .venv/bin/activate 2>/dev/null || { echo "Run install_linux.sh first"; exit 1; }

# ── Phase 5: Voice system dependencies (Linux) ──
echo "==> Installing audio system packages (needs sudo)..."
sudo apt update
sudo apt install -y portaudio19-dev espeak-ng alsa-utils ffmpeg pulseaudio

echo "==> Installing Python voice packages..."
pip install faster-whisper sounddevice numpy pyttsx3 pystray pillow

# ── Optional: Piper neural TTS (much nicer voice than espeak) ──
echo "==> Installing Piper TTS (optional, better voice)..."
mkdir -p ~/.local/bin/piper ~/.nexus/voices
PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz"
if command -v wget &>/dev/null; then
  wget -qO /tmp/piper.tar.gz "$PIPER_URL" && \
    tar -xzf /tmp/piper.tar.gz -C ~/.local/bin/ 2>/dev/null && \
    echo "   Piper binary installed" || echo "   (Piper download skipped — espeak-ng will be used)"
  VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
  wget -qO ~/.nexus/voices/en_US-lessac-medium.onnx "$VOICE_BASE/en_US-lessac-medium.onnx" 2>/dev/null || true
  wget -qO ~/.nexus/voices/en_US-lessac-medium.onnx.json "$VOICE_BASE/en_US-lessac-medium.onnx.json" 2>/dev/null || true
fi

# ── Phase 6: Desktop UI (Tauri) ──
echo "==> Installing Tauri prerequisites..."
sudo apt install -y libwebkit2gtk-4.1-dev libappindicator3-dev \
  librsvg2-dev patchelf libgtk-3-dev libayatana-appindicator3-dev || true

if ! command -v cargo &>/dev/null; then
  echo "==> Installing Rust..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source "$HOME/.cargo/env"
fi

if ! command -v node &>/dev/null; then
  echo "==> Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
fi

echo "==> Generating app icons..."
python generate_icons.py

echo "==> Installing UI npm packages..."
cd ui && npm install && cd ..

echo ""
echo "==> Voice + UI setup complete!"
echo ""
echo "  Test voice (CLI):     python -m voice          # push-to-talk"
echo "                        python -m voice --continuous   # wake word 'nexus'"
echo "  System tray:          python tray.py"
echo "  Desktop app (dev):    cd ui && npm run tauri dev"
echo "  Build installers:     cd ui && npm run tauri build"
echo "                        → .deb + .AppImage in ui/src-tauri/target/release/bundle/"
