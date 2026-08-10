$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$hook = Join-Path $repo '.git\hooks\pre-commit'
$content = "#!/bin/sh`nexec ./.venv/Scripts/python.exe ./scripts/privacy_guard.py`n"
[System.IO.File]::WriteAllText($hook, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Installed the HealthVault privacy guard as the Git pre-commit hook.'
