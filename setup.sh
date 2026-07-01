#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# NEXUS OS Bot — one-command setup for backend + frontend
# Creates the venv, installs ALL Python deps, sets up the UI, and
# (optionally) voice + Playwright. Run from the project root:
#     bash setup.sh                 # backend + frontend + voice
#     bash setup.sh --no-voice      # skip heavy voice deps
#     bash setup.sh --backend-only  # skip the frontend (no Node needed)
# ═══════════════════════════════════════════════════════════════════
set -e

VOICE=1
FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --no-voice)     VOICE=0 ;;
    --backend-only) FRONTEND=0 ;;
  esac
done

echo "════════════════════════════════════════"
echo "  NEXUS OS Bot — setup"
echo "════════════════════════════════════════"

# ── 1. Python venv ──
if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

# ── 2. Core backend deps ──
echo "==> Installing core backend dependencies..."
pip install -r requirements.txt

# ── 3. Test deps ──
echo "==> Installing test dependencies..."
pip install -r requirements-dev.txt

# ── 4. Playwright browser (for Phase 3 browser automation) ──
echo "==> Installing Playwright Chromium..."
python -m playwright install chromium || echo "   (skipped — run later: python -m playwright install chromium)"
if [ "$(uname)" = "Linux" ]; then
  python -m playwright install-deps chromium 2>/dev/null || \
    echo "   (browser system deps need sudo — run: sudo python -m playwright install-deps chromium)"
fi

# ── 5. Voice deps (optional, heavy) ──
if [ "$VOICE" = "1" ]; then
  echo "==> Installing voice dependencies (Phase 5)..."
  pip install -r requirements-voice.txt
  if [ "$(uname)" = "Linux" ]; then
    echo "   NOTE: voice also needs system audio packages:"
    echo "         sudo apt install portaudio19-dev espeak-ng ffmpeg"
  fi
else
  echo "==> Skipping voice deps (--no-voice)."
fi

# ── 6. Frontend ──
if [ "$FRONTEND" = "1" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "==> Installing frontend (npm) dependencies..."
    ( cd ui && npm install )
    echo "==> Generating app icons..."
    python generate_icons.py 2>/dev/null || echo "   (icon gen skipped)"
  else
    echo "==> npm not found — skipping frontend."
    echo "   Install Node.js 20+ then run:  cd ui && npm install"
  fi
fi

echo ""
echo "════════════════════════════════════════"
echo "  Setup complete!"
echo "════════════════════════════════════════"
echo "  Activate venv:   source .venv/bin/activate"
echo "  Run backend:     python -m api.server"
echo "  Run CLI:         python main.py"
echo "  Run tray:        python tray.py"
if [ "$FRONTEND" = "1" ]; then
  echo "  Run desktop app: cd ui && npm run tauri dev"
fi
echo ""
