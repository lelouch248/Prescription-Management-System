param([switch]$WithVoice)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path $PSScriptRoot).Path
Set-Location $repo

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.12 or newer is required.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 20 or newer is required.' }
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -e '.[dev,ocr]'
if ($WithVoice) { & '.\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -e '.[voice]' }
npm install --no-audit --no-fund
npm run build
& '.\.venv\Scripts\python.exe' -m pytest
& '.\scripts\install_git_hooks.ps1'
Write-Host 'HealthVault Local is installed. Run .\start.ps1 to begin.' -ForegroundColor Green
