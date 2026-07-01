# NEXUS OS Bot — Windows setup (PowerShell)
# Run from project root:  powershell -ExecutionPolicy Bypass -File setup.ps1
Write-Host "==> Creating virtual environment..."
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

Write-Host "==> Installing core backend dependencies..."
pip install -r requirements.txt
pip install -r requirements-dev.txt

Write-Host "==> Installing Playwright Chromium..."
python -m playwright install chromium

Write-Host "==> Installing voice dependencies..."
pip install -r requirements-voice.txt

if (Get-Command npm -ErrorAction SilentlyContinue) {
  Write-Host "==> Installing frontend dependencies..."
  Push-Location ui; npm install; Pop-Location
  python generate_icons.py
} else {
  Write-Host "==> npm not found — install Node.js 20+, then: cd ui; npm install"
}

Write-Host ""
Write-Host "Setup complete! Activate with:  .\.venv\Scripts\Activate.ps1"
Write-Host "Run backend:  python -m api.server"
Write-Host "Desktop app:  cd ui; npm run tauri dev"
