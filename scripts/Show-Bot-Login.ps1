$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m agent_server.bot_runtime --show-login
exit $LASTEXITCODE
