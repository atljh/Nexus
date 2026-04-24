# Nexus Windows Build Script (self-bootstrapping)
#
# One-click build: installs any missing prerequisites (Python, Node.js, pnpm),
# sets up a backend venv, builds the PyInstaller bundle, then builds the
# Electron NSIS installer. Output lands in release\Nexus Setup *.exe.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipBackend
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipFrontend

[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "backend"
$VenvDir    = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-Step($msg)  { Write-Host "==> $msg" -ForegroundColor Blue }
function Write-Ok($msg)    { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Die($msg)         { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Block)
    & $Block
    if ($LASTEXITCODE -ne 0) { Die "$Label failed (exit $LASTEXITCODE)" }
}

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
    # npm's global prefix ($env:APPDATA\npm on Windows) isn't recorded in the
    # registry PATH, so Refresh-Path alone won't expose globally-installed CLIs.
    if ($env:APPDATA) {
        $npmGlobal = Join-Path $env:APPDATA "npm"
        if ((Test-Path $npmGlobal) -and ($env:Path -notlike "*$npmGlobal*")) {
            $env:Path = "$env:Path;$npmGlobal"
        }
    }
}

function Command-Exists($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Test-IsAdmin {
    try {
        $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object System.Security.Principal.WindowsPrincipal($id)
        return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

function Ensure-Winget {
    if (-not (Command-Exists "winget")) {
        Die @"
winget is not available. Install 'App Installer' from the Microsoft Store
(https://apps.microsoft.com/detail/9NBLGGH4NNS1), then re-run this script.
Alternatively, install Python 3.11+ and Node.js 20 LTS manually and re-run.
"@
    }
}

function Install-Winget-Package($id, $label) {
    Ensure-Winget
    Write-Step "Installing $label via winget ($id)"
    winget install --exact --id $id --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -ne 0) { Die "winget failed to install $label (exit $LASTEXITCODE)" }
    Refresh-Path
}

# ------------------------------------------------------------------
# Prerequisite: Python 3.11+
# ------------------------------------------------------------------
function Get-PythonExe {
    foreach ($cmd in @("python", "python3", "py")) {
        $src = (Get-Command $cmd -ErrorAction SilentlyContinue | Select-Object -First 1).Source
        if (-not $src) { continue }
        $ver = & $src --version 2>&1
        if ($ver -match "Python\s+(\d+)\.(\d+)") {
            $maj = [int]$Matches[1]; $min = [int]$Matches[2]
            if ($maj -eq 3 -and $min -ge 11) { return $src }
        }
    }
    return $null
}

function Ensure-Python {
    $py = Get-PythonExe
    if ($py) { Write-Ok "Python found: $py"; return $py }
    Write-Warn2 "Python 3.11+ not found"
    Install-Winget-Package "Python.Python.3.11" "Python 3.11"
    $py = Get-PythonExe
    if (-not $py) {
        Die "Python 3.11 was installed but is not on PATH. Close this window, open a new PowerShell, and re-run the script."
    }
    Write-Ok "Python installed: $py"
    return $py
}

# ------------------------------------------------------------------
# Prerequisite: Git (needed for git+ pip requirements)
# ------------------------------------------------------------------
function Ensure-Git {
    if (Command-Exists "git") {
        Write-Ok "Git found: $(& git --version)"
        return
    }
    Write-Warn2 "Git not found"
    Install-Winget-Package "Git.Git" "Git"
    if (-not (Command-Exists "git")) {
        Die "Git was installed but is not on PATH. Open a new PowerShell and re-run the script."
    }
    Write-Ok "Git installed: $(& git --version)"
}

# ------------------------------------------------------------------
# Prerequisite: Node.js LTS
# ------------------------------------------------------------------
function Ensure-Node {
    if (Command-Exists "node") {
        Write-Ok "Node found: $(& node --version)"
        return
    }
    Write-Warn2 "Node.js not found"
    Install-Winget-Package "OpenJS.NodeJS.LTS" "Node.js LTS"
    if (-not (Command-Exists "node")) {
        Die "Node.js was installed but is not on PATH. Open a new PowerShell and re-run the script."
    }
    Write-Ok "Node installed: $(& node --version)"
}

# ------------------------------------------------------------------
# Prerequisite: pnpm
# ------------------------------------------------------------------
function Ensure-Pnpm {
    if (Command-Exists "pnpm") {
        Write-Ok "pnpm found: $(& pnpm --version)"
        return
    }
    Write-Step "Installing pnpm via npm"
    Invoke-Checked "npm install -g pnpm" { npm install -g pnpm }
    Refresh-Path
    if (-not (Command-Exists "pnpm")) {
        Die "pnpm was installed but is not on PATH. Open a new PowerShell and re-run the script."
    }
    Write-Ok "pnpm installed: $(& pnpm --version)"
}

# ==================================================================
Write-Host "+=================================+" -ForegroundColor Blue
Write-Host "|    Nexus Windows Build (auto)   |" -ForegroundColor Blue
Write-Host "+=================================+" -ForegroundColor Blue
Write-Host ""

Set-Location $ProjectDir

# ------------------------------------------------------------------
# Pre-flight: detect missing system prerequisites up front so we can
# fail fast with a clear message if the user lacks admin rights.
# ------------------------------------------------------------------
$missing = @()
if (-not $SkipBackend) {
    if (-not (Get-PythonExe))   { $missing += "Python 3.11 (winget: Python.Python.3.11)" }
    if (-not (Command-Exists "git")) { $missing += "Git (winget: Git.Git)" }
}
if (-not $SkipFrontend) {
    if (-not (Command-Exists "node")) { $missing += "Node.js LTS (winget: OpenJS.NodeJS.LTS)" }
}

if ($missing.Count -gt 0) {
    Write-Warn2 "Missing prerequisites:"
    foreach ($m in $missing) { Write-Host "      - $m" -ForegroundColor Yellow }
    if (-not (Test-IsAdmin)) {
        Die @"
These need to be installed via winget, which usually requires Administrator.
Re-run this script from an elevated PowerShell:
  1. Close this window.
  2. Start menu -> "PowerShell" -> right-click -> "Run as administrator".
  3. cd to the project and run: powershell -ExecutionPolicy Bypass -File scripts\build.ps1
After the one-time install you can run future builds without admin.
"@
    }
    Write-Warn2 "Running as Administrator, will install the missing prerequisites."
}

# ------------------------------------------------------------------
# 1. Backend (PyInstaller)
# ------------------------------------------------------------------
if (-not $SkipBackend) {
    Write-Step "[1/3] Preparing Python backend"

    $python = Ensure-Python
    Ensure-Git

    if (-not (Test-Path $VenvPython)) {
        Write-Step "Creating virtualenv at $VenvDir"
        Invoke-Checked "python -m venv" { & $python -m venv $VenvDir }
    }
    if (-not (Test-Path $VenvPython)) { Die "venv python not found at $VenvPython" }
    Write-Ok "venv: $VenvPython"

    Write-Step "Installing backend dependencies (first run: a few minutes)"
    $req = Join-Path $BackendDir "requirements.txt"
    Invoke-Checked "pip upgrade"     { & $VenvPython -m pip install --upgrade pip }
    Invoke-Checked "pip install -r"  { & $VenvPython -m pip install -r $req }
    Invoke-Checked "pip pyinstaller" { & $VenvPython -m pip install pyinstaller }

    Write-Step "Running PyInstaller"
    Push-Location $BackendDir
    try {
        if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
        if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }

        if (Test-Path "main.spec") {
            Invoke-Checked "pyinstaller main.spec" {
                & $VenvPython -m PyInstaller -y main.spec
            }
        } else {
            Invoke-Checked "pyinstaller main.py" {
                & $VenvPython -m PyInstaller -y --onedir --name main `
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
            }
        }
    }
    finally { Pop-Location }

    $BackendDist = Join-Path $ProjectDir "backend-dist"
    New-Item -ItemType Directory -Force -Path $BackendDist | Out-Null
    $DestMain = Join-Path $BackendDist "main"
    if (Test-Path $DestMain) { Remove-Item -Recurse -Force $DestMain }
    $SrcMain = Join-Path $BackendDir "dist\main"
    if (-not (Test-Path $SrcMain)) { Die "PyInstaller output not found at $SrcMain" }
    Copy-Item -Recurse $SrcMain $DestMain

    $MainExe = Join-Path $DestMain "main.exe"
    if (-not (Test-Path $MainExe)) { Die "main.exe not produced by PyInstaller (looked at $MainExe)" }
    Write-Ok "Backend bundled: $MainExe"
}
else {
    Write-Warn2 "[1/3] -SkipBackend set, reusing backend-dist\"
}

# ------------------------------------------------------------------
# 2. Frontend + Electron installer
# ------------------------------------------------------------------
if (-not $SkipFrontend) {
    Write-Step "[2/3] Preparing Node toolchain"
    Ensure-Node
    Ensure-Pnpm

    Write-Step "Installing frontend dependencies (first run: several minutes)"
    Set-Location $ProjectDir
    Invoke-Checked "pnpm install" { pnpm install }

    Write-Step "Building frontend and NSIS installer"
    Invoke-Checked "pnpm run package:win" { pnpm run package:win }
}
else {
    Write-Warn2 "[2/3] -SkipFrontend set, skipping electron-builder"
}

# ------------------------------------------------------------------
# 3. Report
# ------------------------------------------------------------------
Write-Step "[3/3] Build complete"
$ReleaseDir = Join-Path $ProjectDir "release"
if (Test-Path $ReleaseDir) {
    $installer = Get-ChildItem -Path $ReleaseDir -Filter "*.exe" -File `
        | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($installer) {
        Write-Ok "Installer: $($installer.FullName)"
    } else {
        Write-Warn2 "No .exe found in $ReleaseDir"
    }
    Write-Host ""
    Write-Host "Output directory: $ReleaseDir" -ForegroundColor Green
}
Write-Host ""
