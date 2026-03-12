# Nexus Build Script for Windows
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build.ps1

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "backend"

Write-Host "+=================================+" -ForegroundColor Blue
Write-Host "|         Nexus Build (Win)       |" -ForegroundColor Blue
Write-Host "+=================================+" -ForegroundColor Blue
Write-Host ""

Set-Location $ProjectDir

# --- Step 1: Build Python backend ---
Write-Host "[1/3] Building Python backend..." -ForegroundColor Yellow

Set-Location $BackendDir

# Activate venv
$VenvActivate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
if (-Not (Test-Path $VenvActivate)) {
    Write-Host "ERROR: Python venv not found at $VenvActivate" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt pyinstaller" -ForegroundColor Yellow
    exit 1
}
& $VenvActivate

pyinstaller -y --onedir --name main `
    --hidden-import=aiosqlite `
    --hidden-import=uvicorn.logging `
    --hidden-import=uvicorn.loops `
    --hidden-import=uvicorn.loops.auto `
    --hidden-import=uvicorn.protocols `
    --hidden-import=uvicorn.protocols.http `
    --hidden-import=uvicorn.protocols.http.auto `
    --hidden-import=uvicorn.protocols.websockets `
    --hidden-import=uvicorn.protocols.websockets.auto `
    --hidden-import=uvicorn.lifespan `
    --hidden-import=uvicorn.lifespan.on `
    "--add-data=database;database" `
    "--add-data=api;api" `
    "--add-data=telegram;telegram" `
    main.py

if ($LASTEXITCODE -ne 0) { exit 1 }

# Move to backend-dist
$BackendDist = Join-Path $ProjectDir "backend-dist"
New-Item -ItemType Directory -Force -Path $BackendDist | Out-Null
$DestMain = Join-Path $BackendDist "main"
if (Test-Path $DestMain) { Remove-Item -Recurse -Force $DestMain }
Copy-Item -Recurse (Join-Path $BackendDir "dist\main") $DestMain

Write-Host "  Backend built" -ForegroundColor Green

# --- Step 2: Build frontend + Electron ---
Set-Location $ProjectDir

Write-Host "[2/3] Building frontend..." -ForegroundColor Yellow

if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm run build:win
} else {
    npm run build:win
}

if ($LASTEXITCODE -ne 0) { exit 1 }

# --- Done ---
Write-Host "[3/3] Build complete!" -ForegroundColor Yellow
Write-Host ""
Write-Host "Output: $ProjectDir\release\" -ForegroundColor Green
Write-Host ""
