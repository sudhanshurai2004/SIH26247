# Locked Windows setup for the offline trainer source checkout.
# Equivalent to the POSIX `make setup` target, using Windows virtualenv paths.
[CmdletBinding()]
param(
    [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pythonLauncher = Get-Command py -ErrorAction Stop
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pythonLauncher.Path "-$PythonVersion" -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -r requirements-dev.lock
npm --prefix dashboard ci

Write-Host "WINDOWS_SETUP_OK: locked Python and dashboard dependencies installed"
