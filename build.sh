#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# NEXUS OS Bot — build script
# Produces distributable desktop installers via Tauri, and optionally
# bundles the Python backend so end users don't need Python installed.
#
# Usage:
#   bash build.sh                  # build desktop app for the current OS
#   bash build.sh --debug          # faster debug build (not for release)
#   bash build.sh --backend        # also bundle the Python backend (PyInstaller)
#   bash build.sh --frontend-only  # just the Vite frontend (dist/), no Tauri
#   bash build.sh --clean          # remove previous build artifacts first
# ═══════════════════════════════════════════════════════════════════
set -e

MODE="release"
BUILD_BACKEND=0
FRONTEND_ONLY=0
CLEAN=0

for arg in "$@"; do
  case "$arg" in
    --debug)         MODE="debug" ;;
    --backend)       BUILD_BACKEND=1 ;;
    --frontend-only) FRONTEND_ONLY=1 ;;
    --clean)         CLEAN=1 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "════════════════════════════════════════"
echo "  NEXUS OS Bot — build ($MODE)"
echo "════════════════════════════════════════"

# ── 0. Detect OS for friendly messaging ──
OS="$(uname -s)"
case "$OS" in
  Linux)  PLATFORM="Linux  → .deb + .AppImage + .rpm" ;;
  Darwin) PLATFORM="macOS  → .dmg + .app" ;;
  *)      PLATFORM="$OS" ;;
esac
echo "  Target platform: $PLATFORM"
echo ""

# ── 1. Prerequisite checks ──
echo "==> Checking prerequisites..."
MISSING=0

if ! command -v node >/dev/null 2>&1; then
  echo "   ✗ Node.js not found. Install Node 20+: https://nodejs.org"
  MISSING=1
else
  echo "   ✓ Node $(node --version)"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "   ✗ npm not found."
  MISSING=1
else
  echo "   ✓ npm $(npm --version)"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "   ✗ Rust/cargo not found. Install: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
  MISSING=1
else
  echo "   ✓ cargo $(cargo --version | awk '{print $2}')"
fi

# Linux-only Tauri system libs
if [ "$OS" = "Linux" ] && [ "$FRONTEND_ONLY" = "0" ]; then
  if ! pkg-config --exists webkit2gtk-4.1 2>/dev/null; then
    echo "   ✗ webkit2gtk-4.1 dev libs missing. Install:"
    echo "       sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev \\"
    echo "         librsvg2-dev patchelf libgtk-3-dev libayatana-appindicator3-dev"
    MISSING=1
  else
    echo "   ✓ webkit2gtk-4.1 present"
  fi
fi

if [ "$MISSING" = "1" ]; then
  echo ""
  echo "   Install the missing tools above, then re-run.  Aborting."
  exit 1
fi
echo ""

# ── 2. Clean if asked ──
if [ "$CLEAN" = "1" ]; then
  echo "==> Cleaning previous artifacts..."
  rm -rf ui/dist ui/src-tauri/target/release/bundle dist_backend build_backend *.spec
  echo ""
fi

# ── 3. Generate icons (Tauri requires them) ──
if [ -f generate_icons.py ]; then
  echo "==> Generating app icons..."
  PY="python3"
  [ -x ".venv/bin/python" ] && PY=".venv/bin/python"
  $PY generate_icons.py || echo "   (icon gen skipped — install Pillow: pip install pillow)"
  echo ""
fi

# ── 4. Optionally bundle the Python backend with PyInstaller ──
if [ "$BUILD_BACKEND" = "1" ]; then
  echo "==> Bundling Python backend (PyInstaller)..."
  PY="python3"
  [ -x ".venv/bin/python" ] && PY=".venv/bin/python"
  $PY -m pip install --quiet pyinstaller
  # Build a single-folder backend executable that runs the API server
  $PY -m PyInstaller \
    --name nexus-backend \
    --distpath dist_backend \
    --workpath build_backend \
    --specpath . \
    --noconfirm \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.protocols.websockets.auto \
    --hidden-import uvicorn.lifespan.on \
    --collect-all fastapi \
    --collect-all starlette \
    backend_entry.py
  echo "   Backend bundled → dist_backend/nexus-backend/"
  echo ""
fi

# ── 5. Install frontend deps ──
echo "==> Installing frontend dependencies..."
( cd ui && npm install )
echo ""

# ── 6. Build ──
if [ "$FRONTEND_ONLY" = "1" ]; then
  echo "==> Building frontend only (Vite)..."
  ( cd ui && npm run build )
  echo ""
  echo "   Frontend built → ui/dist/"
  exit 0
fi

echo "==> Building desktop app with Tauri ($MODE)..."
echo "   (first build compiles many Rust crates — can take 5–15 min)"
if [ "$MODE" = "debug" ]; then
  ( cd ui && npm run tauri build -- --debug )
  BUNDLE_DIR="ui/src-tauri/target/debug/bundle"
else
  ( cd ui && npm run tauri build )
  BUNDLE_DIR="ui/src-tauri/target/release/bundle"
fi

# ── 7. Report artifacts ──
echo ""
echo "════════════════════════════════════════"
echo "  Build complete!"
echo "════════════════════════════════════════"
if [ -d "$BUNDLE_DIR" ]; then
  echo "  Installers created in:"
  echo "    $BUNDLE_DIR"
  echo ""
  find "$BUNDLE_DIR" -type f \( -name "*.deb" -o -name "*.AppImage" -o -name "*.rpm" \
    -o -name "*.dmg" -o -name "*.app" -o -name "*.exe" -o -name "*.msi" \) \
    2>/dev/null | while read -r f; do
      SIZE=$(du -h "$f" | cut -f1)
      echo "    • $(basename "$f")  ($SIZE)"
    done
else
  echo "  (bundle dir not found — check the Tauri output above for errors)"
fi
echo ""
