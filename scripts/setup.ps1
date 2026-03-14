# Nexus Initial Setup Script for Windows
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "backend"

Write-Host "+=================================+" -ForegroundColor Blue
Write-Host "|       Nexus Setup (Windows)     |" -ForegroundColor Blue
Write-Host "+=================================+" -ForegroundColor Blue
Write-Host ""

Set-Location $ProjectDir

# ── Check requirements ──────────────────────────────────────────

Write-Host "Checking requirements..." -ForegroundColor Yellow
Write-Host ""

# Python
$PythonCmd = $null
foreach ($cmd in @("python3.12", "python3.11", "python3", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.") {
            $PythonCmd = $cmd
            break
        }
    }
}
if (-not $PythonCmd) {
    Write-Host "  X Python 3 is not installed" -ForegroundColor Red
    Write-Host "    Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
Write-Host "  + Python: $(& $PythonCmd --version)" -ForegroundColor Green

# Git (needed for tdesktop-decrypter)
$HasGit = Get-Command git -ErrorAction SilentlyContinue
if ($HasGit) {
    Write-Host "  + Git: $(git --version)" -ForegroundColor Green
} else {
    Write-Host "  ! Git not found (will use zip fallback for some packages)" -ForegroundColor Yellow
}

# Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "  X Node.js is not installed" -ForegroundColor Red
    Write-Host "    Download: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}
Write-Host "  + Node.js: $(node --version)" -ForegroundColor Green

# pnpm
$PkgManager = "npm"
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    Write-Host "  + pnpm: $(pnpm --version)" -ForegroundColor Green
    $PkgManager = "pnpm"
} else {
    Write-Host "  ! pnpm not found, using npm" -ForegroundColor Yellow
}

# ── Python environment ──────────────────────────────────────────

Write-Host ""
Write-Host "Setting up Python environment..." -ForegroundColor Yellow

$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$ReqFile = Join-Path $BackendDir "requirements.txt"
$DepsMarker = Join-Path $VenvDir ".deps_installed"

# Create venv
if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating virtual environment..."
    & $PythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  X Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "  + Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  + Virtual environment exists" -ForegroundColor Green
}

# Upgrade pip
Write-Host "  Upgrading pip..."
& $VenvPython -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X Failed to upgrade pip" -ForegroundColor Red
    exit 1
}

# Install requirements (handle git dependency fallback)
Write-Host "  Installing Python dependencies..."

# Try normal install first
& $VenvPython -m pip install -r $ReqFile -q 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ! Some dependencies failed, trying with fallback..." -ForegroundColor Yellow

    # Install everything except git-based deps
    $TempReq = Join-Path $env:TEMP "nexus_requirements_temp.txt"
    Get-Content $ReqFile | Where-Object { $_ -notmatch "git\+" } | Set-Content $TempReq
    & $VenvPython -m pip install -r $TempReq -q
    Remove-Item $TempReq -ErrorAction SilentlyContinue

    # Install tdesktop-decrypter via zip (no git required)
    Write-Host "  Installing tdesktop-decrypter (zip fallback)..."
    & $VenvPython -m pip install "https://github.com/ntqbit/tdesktop-decrypter/archive/refs/heads/master.zip" -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  X Failed to install tdesktop-decrypter" -ForegroundColor Red
        Write-Host "    Try manually: .venv\Scripts\pip install https://github.com/ntqbit/tdesktop-decrypter/archive/refs/heads/master.zip" -ForegroundColor Yellow
    }
}

# Verify tdesktop-decrypter
$TdDecrypter = Join-Path $VenvDir "Scripts\tdesktop-decrypter.exe"
if (Test-Path $TdDecrypter) {
    Write-Host "  + tdesktop-decrypter installed" -ForegroundColor Green
} else {
    Write-Host "  ! tdesktop-decrypter not found in venv" -ForegroundColor Yellow
    Write-Host "    TData import will not work without it" -ForegroundColor Yellow
}

New-Item -ItemType File -Force -Path $DepsMarker | Out-Null
Write-Host "  + Python dependencies installed" -ForegroundColor Green

# ── Node.js environment ────────────────────────────────────────

Write-Host ""
Write-Host "Setting up Node.js environment..." -ForegroundColor Yellow

if ($PkgManager -eq "pnpm") {
    pnpm install
} else {
    npm install
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X Failed to install Node.js dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "  + Node.js dependencies installed" -ForegroundColor Green

# ── Done ────────────────────────────────────────────────────────

Write-Host ""
Write-Host "+=================================+" -ForegroundColor Green
Write-Host "|        Setup Complete!          |" -ForegroundColor Green
Write-Host "+=================================+" -ForegroundColor Green
Write-Host ""
Write-Host "Run: " -NoNewline
Write-Host "powershell -File scripts\dev.ps1" -ForegroundColor Blue -NoNewline
Write-Host " to start development"
Write-Host ""
