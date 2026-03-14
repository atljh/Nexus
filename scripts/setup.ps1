# Nexus Setup Script for Windows
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "backend"

Write-Host ""
Write-Host "  Nexus Setup" -ForegroundColor Cyan
Write-Host "  ==========" -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectDir

# ── 1. Check Python ─────────────────────────────────────────────

$PythonCmd = $null
foreach ($cmd in @("python", "python3", "python3.12", "python3.11")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.") {
            $PythonCmd = $cmd
            break
        }
    } catch {}
}
if (-not $PythonCmd) {
    Write-Host "  [X] Python 3 not found. Download: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
Write-Host "  [+] $((& $PythonCmd --version 2>&1))" -ForegroundColor Green

# ── 2. Check Node.js ────────────────────────────────────────────

try { $null = Get-Command node -ErrorAction Stop } catch {
    Write-Host "  [X] Node.js not found. Download: https://nodejs.org/" -ForegroundColor Red
    exit 1
}
Write-Host "  [+] Node.js $(node --version)" -ForegroundColor Green

$PkgManager = "npm"
try {
    $null = Get-Command pnpm -ErrorAction Stop
    $PkgManager = "pnpm"
    Write-Host "  [+] pnpm $(pnpm --version)" -ForegroundColor Green
} catch {
    Write-Host "  [!] pnpm not found, using npm" -ForegroundColor Yellow
}

# ── 3. Python venv ──────────────────────────────────────────────

Write-Host ""
Write-Host "  Setting up Python..." -ForegroundColor Cyan

$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile = Join-Path $BackendDir "requirements.txt"

if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating venv..." -ForegroundColor Gray
    & $PythonCmd -m venv $VenvDir
    if (-not (Test-Path $VenvPython)) {
        Write-Host "  [X] Failed to create venv" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  [+] venv ready" -ForegroundColor Green

# ── 4. Install ALL pip packages ─────────────────────────────────

Write-Host "  Upgrading pip..." -ForegroundColor Gray
& $VenvPython -m pip install --upgrade pip -q 2>&1 | Out-Null

Write-Host "  Installing dependencies..." -ForegroundColor Gray

# Install everything from requirements.txt line by line to handle failures gracefully
$lines = Get-Content $ReqFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith("#") }
$failed = @()

foreach ($pkg in $lines) {
    # Skip git-based deps for now (handle separately)
    if ($pkg -match "git\+") { continue }

    & $VenvPython -m pip install $pkg -q 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $failed += $pkg
        Write-Host "  [!] Failed: $pkg" -ForegroundColor Yellow
    }
}

# tdesktop-decrypter: try git, then zip
Write-Host "  Installing tdesktop-decrypter..." -ForegroundColor Gray
& $VenvPython -m pip install "telegram-desktop-decrypter@git+https://github.com/ntqbit/tdesktop-decrypter.git" -q 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install "https://github.com/ntqbit/tdesktop-decrypter/archive/refs/heads/master.zip" -q 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $failed += "tdesktop-decrypter"
    }
}

# ── 5. Verify critical packages ─────────────────────────────────

Write-Host ""
Write-Host "  Verifying packages..." -ForegroundColor Cyan

$checks = @(
    @("fastapi",    "import fastapi"),
    @("telethon",   "import telethon"),
    @("socks",      "import socks"),
    @("PySocks",    "import socks; print(f'PySocks {socks.__version__}')"),
    @("sqlalchemy", "import sqlalchemy"),
    @("aiosqlite",  "import aiosqlite"),
    @("cryptg",     "import cryptg"),
    @("aiohttp",    "import aiohttp"),
    @("httpx",      "import httpx"),
    @("tdesktop",   "import subprocess; import shutil; assert shutil.which('tdesktop-decrypter', path=r'$($VenvDir)\Scripts')")
)

foreach ($check in $checks) {
    $name = $check[0]
    $code = $check[1]
    $result = & $VenvPython -c $code 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [+] $name" -ForegroundColor Green
    } else {
        Write-Host "  [X] $name - MISSING" -ForegroundColor Red
    }
}

# ── 6. Node.js dependencies ─────────────────────────────────────

Write-Host ""
Write-Host "  Setting up Node.js..." -ForegroundColor Cyan

Set-Location $ProjectDir
if ($PkgManager -eq "pnpm") {
    pnpm install 2>&1 | Out-Null
} else {
    npm install 2>&1 | Out-Null
}
Write-Host "  [+] Node modules installed" -ForegroundColor Green

# Mark deps as installed
New-Item -ItemType File -Force -Path (Join-Path $VenvDir ".deps_installed") | Out-Null

# ── Done ─────────────────────────────────────────────────────────

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "  Setup complete with warnings:" -ForegroundColor Yellow
    foreach ($f in $failed) {
        Write-Host "    - $f" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Setup complete!" -ForegroundColor Green
}
Write-Host ""
Write-Host "  Start: pnpm dev" -ForegroundColor Cyan
Write-Host ""
