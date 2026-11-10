param([switch]$WithAstrBot)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 environment creation failed' }
}
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonPath -m pip install -r agent_server\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if ($WithAstrBot) {
    & $pythonPath -m pip install -r integrations\astrbot-requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'AstrBot installation failed' }
}
& $pythonPath -m agent_server.configure
& $pythonPath -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed' }
Write-Output 'Setup complete. Run scripts\Start-Agent.ps1.'
