#!/usr/bin/env bash
# NEXUS OS Bot — Linux installer
# Run from the project root:  bash install_linux.sh
set -e

echo "==> NEXUS OS Bot — Linux setup"

# 1. System packages
echo "==> Installing system dependencies (needs sudo)..."
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential curl wget git \
  xdotool wmctrl xclip \
  ffmpeg alsa-utils \
  libgbm1 libnss3 libasound2t64 2>/dev/null || \
sudo apt install -y libasound2

# 2. Python virtual environment
echo "==> Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 3. Python dependencies
echo "==> Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Playwright browser (Phase 3)
echo "==> Installing Playwright Chromium..."
python -m playwright install chromium
python -m playwright install-deps chromium

# 5. Ollama
if ! command -v ollama &>/dev/null; then
  echo "==> Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

# 6. Pull a model sized to this machine's RAM
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
echo "==> Detected ${RAM_GB} GB RAM"
ollama serve &>/dev/null &
sleep 3
if   [ "$RAM_GB" -ge 16 ]; then ollama pull llama3.1:8b
elif [ "$RAM_GB" -ge 8  ]; then ollama pull llama3.2:3b
else                            ollama pull phi3:mini
fi

echo ""
echo "==> Setup complete!"
echo "    Activate:  source .venv/bin/activate"
echo "    Run CLI:   python main.py"
echo "    Run API:   python -m api.server"
