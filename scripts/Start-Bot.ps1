$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts\Setup.ps1 -WithAstrBot first.' }
$env:PYTHONIOENCODING = 'utf-8'
& $pythonPath -m agent_server.bot_runtime
exit $LASTEXITCODE
