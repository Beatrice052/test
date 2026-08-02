$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$logDir = Join-Path $projectRoot '.cache\dev'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

foreach ($commandName in @('uv', 'node', 'npm.cmd')) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command is missing: $commandName"
    }
}
$requiredNode = (Get-Content (Join-Path $projectRoot '.node-version') -Raw).Trim()
$actualNode = (& node --version).TrimStart('v')
if ($actualNode -ne $requiredNode) {
    throw "Node.js $requiredNode is required; detected $actualNode."
}
$env:UV_CACHE_DIR = Join-Path $projectRoot '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.cache\uv-python'
$env:npm_config_cache = Join-Path $projectRoot '.cache\npm'
$env:APP_ENV = 'local'
$env:CHATBI_IDENTITY_MODE = 'mock'
$env:CHATBI_LLM_MODE = 'rule_based'
$env:CHATBI_GATEWAY_MODE = 'mock'

Push-Location $backendDir
try {
    & uv sync --all-groups --locked
    if ($LASTEXITCODE -ne 0) { throw 'Backend lockfile install failed.' }
    & uv run python -m app.cli semantic compile `
        --input-dir (Join-Path $projectRoot 'semantic-input\mock') `
        --output-dir (Join-Path $projectRoot 'compiled-semantic\mock')
    if ($LASTEXITCODE -ne 0) { throw 'Mock Semantic compile failed.' }
    & uv run alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally {
    Pop-Location
}
Push-Location $frontendDir
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lockfile install failed.' }
} finally {
    Pop-Location
}

$backendJob = $null
$frontendJob = $null
try {
    $backendJob = Start-Job -ScriptBlock {
        param($Python, $WorkingDirectory, $Stdout, $Stderr)
        Set-Location $WorkingDirectory
        & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 1>$Stdout 2>$Stderr
    } -ArgumentList `
        (Join-Path $backendDir '.venv\Scripts\python.exe'), $backendDir, `
        (Join-Path $logDir 'backend.stdout.log'), (Join-Path $logDir 'backend.stderr.log')
    $npmCommand = (Get-Command npm.cmd).Source
    $frontendJob = Start-Job -ScriptBlock {
        param($Npm, $WorkingDirectory, $Stdout, $Stderr)
        Set-Location $WorkingDirectory
        & $Npm run dev -- --host 127.0.0.1 --port 5173 1>$Stdout 2>$Stderr
    } -ArgumentList `
        $npmCommand, $frontendDir, `
        (Join-Path $logDir 'frontend.stdout.log'), (Join-Path $logDir 'frontend.stderr.log')

    & (Join-Path $backendDir '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'wait_http.py') `
        'http://127.0.0.1:8000/api/v1/health/ready' --timeout-seconds 30
    if ($LASTEXITCODE -ne 0) { throw 'Backend did not become ready.' }
    & (Join-Path $backendDir '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'wait_http.py') `
        'http://127.0.0.1:5173' --timeout-seconds 30
    if ($LASTEXITCODE -ne 0) { throw 'Frontend did not become ready.' }

    Write-Host 'Backend: http://127.0.0.1:8000'
    Write-Host 'Frontend: http://127.0.0.1:5173'
    Write-Host "Logs: $logDir"
    Write-Host 'Press Ctrl+C to stop both processes.'
    while ($backendJob.State -eq 'Running' -and $frontendJob.State -eq 'Running') {
        Start-Sleep -Seconds 1
    }
    throw "A development service stopped unexpectedly. Logs: $logDir"
} finally {
    foreach ($job in @($backendJob, $frontendJob)) {
        if ($null -ne $job) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }
    }
}
