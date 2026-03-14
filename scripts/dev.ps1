# Nexus Development Startup Script for Windows
# Usage: powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "backend"

Write-Host "+=================================+" -ForegroundColor Blue
Write-Host "|      Nexus Development (Win)    |" -ForegroundColor Blue
Write-Host "+=================================+" -ForegroundColor Blue
Write-Host ""

Set-Location $ProjectDir

# --- Step 1: Check Python ---
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
$PythonCmd = $null
foreach ($cmd in @("python3.12", "python3.11", "python3", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $PythonCmd = $cmd
        break
    }
}
if (-not $PythonCmd) {
    Write-Host "Error: Python 3 is not installed" -ForegroundColor Red
    exit 1
}
$PythonVersion = & $PythonCmd --version
Write-Host "  $PythonVersion" -ForegroundColor Green

# --- Step 2: Setup Python venv ---
Write-Host "[2/4] Setting up Python environment..." -ForegroundColor Yellow
$VenvDir = Join-Path $BackendDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating virtual environment..."
    & $PythonCmd -m venv $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$DepsMarker = Join-Path $VenvDir ".deps_installed"
$ReqFile = Join-Path $BackendDir "requirements.txt"

if ((-not (Test-Path $DepsMarker)) -or ((Get-Item $ReqFile).LastWriteTime -gt (Get-Item $DepsMarker).LastWriteTime)) {
    Write-Host "  Installing Python dependencies..."
    & $VenvPython -m pip install -q --upgrade pip
    & $VenvPython -m pip install -q -r $ReqFile 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Retrying with zip fallback for git deps..." -ForegroundColor Yellow
        $TempReq = Join-Path $env:TEMP "nexus_req_temp.txt"
        Get-Content $ReqFile | Where-Object { $_ -notmatch "git\+" } | Set-Content $TempReq
        & $VenvPython -m pip install -q -r $TempReq
        Remove-Item $TempReq -ErrorAction SilentlyContinue
        & $VenvPython -m pip install -q "https://github.com/ntqbit/tdesktop-decrypter/archive/refs/heads/master.zip" 2>$null
    }
    New-Item -ItemType File -Force -Path $DepsMarker | Out-Null
    Write-Host "  Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  Dependencies up to date" -ForegroundColor Green
}

# --- Step 3: Check Node.js ---
Write-Host "[3/4] Checking Node.js..." -ForegroundColor Yellow
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Node.js is not installed" -ForegroundColor Red
    exit 1
}
$NodeVersion = node --version
Write-Host "  Node.js $NodeVersion" -ForegroundColor Green

# Install Node dependencies if needed
$NodeModules = Join-Path $ProjectDir "node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "  Installing Node.js dependencies..."
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        pnpm install --silent
    } else {
        npm install --silent
    }
    Write-Host "  Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  Dependencies up to date" -ForegroundColor Green
}

# --- Step 4: Start dev servers ---
Write-Host "[4/4] Starting development servers..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Starting Nexus..." -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Blue
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Blue
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm dev
} else {
    npm run dev
}
