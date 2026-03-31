# Home Assistant — Windows Service Uninstaller
# Run as Administrator

param(
    [string]$ServiceName = "PersonalAssistant"
)

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Write-Error "Run this script as Administrator."
    exit 1
}

$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Error "NSSM not found. Install it with: winget install nssm"
    exit 1
}

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Service '$ServiceName' not found — nothing to remove."
    exit 0
}

Write-Host "Stopping and removing '$ServiceName' service..."
& nssm stop $ServiceName 2>$null
& nssm remove $ServiceName confirm
Write-Host "✓  Service removed."
