param([switch]$Lan, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path $PSScriptRoot).Path
Set-Location $repo

if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run .\install.ps1 first.' }
if (-not (Test-Path 'dist\index.html')) { npm run build }
$env:HEALTHVAULT_HOST = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
$env:HEALTHVAULT_PORT = if ($env:HEALTHVAULT_PORT) { $env:HEALTHVAULT_PORT } else { '8765' }
$url = "http://127.0.0.1:$($env:HEALTHVAULT_PORT)"
if (-not $NoBrowser) { Start-Process $url }
Write-Host "HealthVault Local is opening at $url" -ForegroundColor Green
if ($Lan) { Write-Warning 'LAN mode is enabled. Confirm a vault password exists and allow only Private networks in Windows Firewall.' }
& '.\.venv\Scripts\python.exe' -m uvicorn backend.main:app --app-dir src --host $env:HEALTHVAULT_HOST --port ([int]$env:HEALTHVAULT_PORT)
