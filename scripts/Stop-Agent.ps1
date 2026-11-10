$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m agent_server.control --stop
exit $LASTEXITCODE
