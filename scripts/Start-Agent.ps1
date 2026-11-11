param([switch]$Background, [switch]$Watch)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts\Setup.ps1 first.' }
if (-not (Test-Path -LiteralPath '.env')) { & $pythonPath -m agent_server.configure }
$env:PYTHONIOENCODING = 'utf-8'
$agentPort = & $pythonPath -m agent_server.control --port
if ($LASTEXITCODE -ne 0) { throw 'Invalid Agent port configuration.' }
$agentPort = [int]$agentPort
$stopPath = Join-Path $projectRoot 'data\agent.stop'
if (-not $Watch) {
    if (Test-Path -LiteralPath $stopPath) { Remove-Item -LiteralPath $stopPath }
}
if ($Background) {
    if (Get-NetTCPConnection -LocalPort $agentPort -State Listen -ErrorAction SilentlyContinue) {
        & $pythonPath -m agent_server.control
        if ($LASTEXITCODE -ne 0) { throw "Port $agentPort is occupied by an unavailable or unauthorized service." }
        Write-Output "Agent is already listening on port $agentPort."
        exit 0
    }
    $logs = Join-Path $projectRoot 'data\logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $shellPath = (Get-Process -Id $PID).Path
    $process = Start-Process -FilePath $shellPath -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"'),'-Watch') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'agent-watch.stdout.log') -RedirectStandardError (Join-Path $logs 'agent-watch.stderr.log')
    Set-Content -LiteralPath (Join-Path $projectRoot 'data\agent-watch.pid') -Value $process.Id
    Write-Output 'Agent background watcher started.'
    exit 0
}
if (-not $Watch) {
    & $pythonPath -m agent_server.server
    exit $LASTEXITCODE
}
$failures = 0
while (-not (Test-Path -LiteralPath $stopPath)) {
    $started = Get-Date
    & $pythonPath -m agent_server.server
    $code = $LASTEXITCODE
    if ($code -eq 0 -or (Test-Path -LiteralPath $stopPath)) { break }
    if (((Get-Date) - $started).TotalSeconds -gt 60) { $failures = 0 }
    $failures += 1
    if ($failures -ge 5) { throw 'Agent repeatedly failed to start. Check configuration and logs.' }
    Write-Output "Agent exited with code $code. Restarting attempt $failures."
    Start-Sleep -Seconds ([Math]::Min(30, 2 * $failures))
}
