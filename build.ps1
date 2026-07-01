# NEXUS OS Bot — Windows build (PowerShell)
#   powershell -ExecutionPolicy Bypass -File build.ps1
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Backend   # also bundle Python
param([switch]$Debug, [switch]$Backend, [switch]$FrontendOnly, [switch]$Clean)

$ErrorActionPreference = "Stop"
Write-Host "=== NEXUS OS Bot — Windows build ==="

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "  Missing: $cmd  — $hint" -ForegroundColor Red
    return $false
  }
  Write-Host "  OK: $cmd"
  return $true
}

$ok = $true
$ok = (Need "node"  "Install Node 20+: https://nodejs.org") -and $ok
$ok = (Need "npm"   "comes with Node") -and $ok
$ok = (Need "cargo" "Install Rust: https://rustup.rs") -and $ok
if (-not $ok) { Write-Host "Install missing tools, then re-run." -ForegroundColor Red; exit 1 }

$PY = "python"
if (Test-Path ".venv\Scripts\python.exe") { $PY = ".venv\Scripts\python.exe" }

if ($Clean) {
  Write-Host "==> Cleaning..."
  Remove-Item -Recurse -Force ui\dist, ui\src-tauri\target\release\bundle, dist_backend, build_backend -ErrorAction SilentlyContinue
}

if (Test-Path generate_icons.py) {
  Write-Host "==> Generating icons..."
  & $PY generate_icons.py
}

if ($Backend) {
  Write-Host "==> Bundling Python backend (PyInstaller)..."
  & $PY -m pip install --quiet pyinstaller
  & $PY -m PyInstaller --name nexus-backend --distpath dist_backend --workpath build_backend `
    --specpath . --noconfirm `
    --hidden-import uvicorn.logging --hidden-import uvicorn.protocols `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    --collect-all fastapi --collect-all starlette `
    backend_entry.py
}

Write-Host "==> Installing frontend deps..."
Push-Location ui; npm install; Pop-Location

if ($FrontendOnly) {
  Push-Location ui; npm run build; Pop-Location
  Write-Host "Frontend built -> ui\dist\"; exit 0
}

Write-Host "==> Building Tauri app (first build can take 5-15 min)..."
Push-Location ui
if ($Debug) { npm run tauri build -- --debug } else { npm run tauri build }
Pop-Location

Write-Host ""
Write-Host "Build complete. Installers in: ui\src-tauri\target\release\bundle\" -ForegroundColor Green
Get-ChildItem -Recurse ui\src-tauri\target\release\bundle\ -Include *.exe,*.msi -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Host ("  - {0}" -f $_.Name) }
