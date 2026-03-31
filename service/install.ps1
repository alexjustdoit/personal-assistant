# Home Assistant — Windows Service Installer
# Run this script as Administrator (right-click → Run with PowerShell → Yes to elevation)
# Requires NSSM: winget install nssm

param(
    [string]$ServiceName = "PersonalAssistant"
)

# ── Require Administrator ────────────────────────────────────────────────────
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Write-Error "Run this script as Administrator (right-click → Run with PowerShell)."
    exit 1
}

# ── Resolve paths ────────────────────────────────────────────────────────────
$ServiceDir  = Split-Path -Parent $PSScriptRoot  # project root (parent of /service)
$Python      = Join-Path $ServiceDir "venv\Scripts\python.exe"
$Script      = Join-Path $ServiceDir "run.py"
$LogDir      = Join-Path $ServiceDir "data\logs"

if (-not (Test-Path $Python)) {
    Write-Error "venv not found at: $Python`nCreate it first: python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path $Script)) {
    Write-Error "run.py not found at: $Script"
    exit 1
}

if (-not (Test-Path (Join-Path $ServiceDir "config.yaml"))) {
    Write-Error "config.yaml not found. Run setup first: python setup.py"
    exit 1
}

# ── Check NSSM ───────────────────────────────────────────────────────────────
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Error "NSSM not found. Install it with: winget install nssm"
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ── Remove existing service if present ───────────────────────────────────────
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing '$ServiceName' service..."
    & nssm stop $ServiceName 2>$null
    & nssm remove $ServiceName confirm
}

# ── Install service ──────────────────────────────────────────────────────────
Write-Host "Installing '$ServiceName' service..."
& nssm install $ServiceName $Python $Script
& nssm set $ServiceName AppDirectory $ServiceDir
& nssm set $ServiceName DisplayName "Personal Assistant"
& nssm set $ServiceName Description "Personal AI Home Assistant"
& nssm set $ServiceName Start SERVICE_AUTO_START
& nssm set $ServiceName AppStdout (Join-Path $LogDir "assistant.log")
& nssm set $ServiceName AppStderr (Join-Path $LogDir "assistant.log")
& nssm set $ServiceName AppRotateFiles 1
& nssm set $ServiceName AppRotateBytes 5242880  # 5 MB log rotation

# ── Start service ─────────────────────────────────────────────────────────────
Write-Host "Starting service..."
Start-Service $ServiceName

$svc = Get-Service -Name $ServiceName
if ($svc.Status -eq "Running") {
    Write-Host ""
    Write-Host "✓  '$ServiceName' service installed and running."
    Write-Host "   Auto-starts on boot. Access at http://localhost:8000"
    Write-Host ""
    Write-Host "   Gaming toggle:"
    Write-Host "   Stop:  .\service\game_on.bat   (or: Stop-Service $ServiceName)"
    Write-Host "   Start: .\service\game_off.bat  (or: Start-Service $ServiceName)"
} else {
    Write-Warning "Service installed but did not start. Check logs at: $LogDir"
}
