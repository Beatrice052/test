$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$verifyDir = Join-Path $projectRoot '.cache\verify-package'
New-Item -ItemType Directory -Force -Path $verifyDir | Out-Null

foreach ($commandName in @('uv', 'node', 'npm.cmd', 'npx.cmd')) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command is missing: $commandName"
    }
}

$nodeMajor = [int]((& node --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -ne 22) {
    throw "Node.js 22 LTS is required; detected $(& node --version)."
}

$env:UV_CACHE_DIR = Join-Path $projectRoot '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.cache\uv-python'
$env:npm_config_cache = Join-Path $projectRoot '.cache\npm'

Push-Location $backendDir
try {
    & uv sync --all-groups --locked
    if ($LASTEXITCODE -ne 0) { throw 'Backend lockfile install failed.' }
    & uv run ruff check app tests migrations ../scripts
    if ($LASTEXITCODE -ne 0) { throw 'ruff check failed.' }
    & uv run ruff format --check app tests migrations ../scripts
    if ($LASTEXITCODE -ne 0) { throw 'ruff format check failed.' }
    & uv run mypy app
    if ($LASTEXITCODE -ne 0) { throw 'mypy failed.' }
    & uv run pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Backend or G01-G25 tests failed.' }
} finally {
    Pop-Location
}

& uv run --project $backendDir python (Join-Path $projectRoot 'scripts\check_schema_snapshots.py')
if ($LASTEXITCODE -ne 0) { throw 'Schema snapshots drifted.' }
& uv run --project $backendDir python (Join-Path $projectRoot 'scripts\generate_frontend_types.py') --check
if ($LASTEXITCODE -ne 0) { throw 'OpenAPI-generated frontend artifacts drifted.' }
& uv run --project $backendDir python -m app.cli semantic compile `
    --input-dir (Join-Path $projectRoot 'semantic-input\mock') `
    --output-dir (Join-Path $verifyDir 'compiled-semantic')
if ($LASTEXITCODE -ne 0) { throw 'Mock Semantic compile failed.' }

Push-Location $frontendDir
$uiJob = $null
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lockfile install failed.' }
    & npm.cmd run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'Frontend typecheck failed.' }
    & npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lint failed.' }
    & npm.cmd run test -- --run
    if ($LASTEXITCODE -ne 0) { throw 'Frontend unit tests failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    & npx.cmd playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Playwright Chromium install failed.' }
    $uiJob = Start-Job -ScriptBlock {
        param($Python, $WorkingDirectory, $Stdout, $Stderr)
        Set-Location $WorkingDirectory
        & $Python -m http.server 4173 --bind 127.0.0.1 --directory dist 1>$Stdout 2>$Stderr
    } -ArgumentList `
        (Join-Path $backendDir '.venv\Scripts\python.exe'), $frontendDir, `
        (Join-Path $verifyDir 'frontend.stdout.log'), (Join-Path $verifyDir 'frontend.stderr.log')
    & (Join-Path $backendDir '.venv\Scripts\python.exe') (Join-Path $projectRoot 'scripts\wait_http.py') `
        'http://127.0.0.1:4173' --timeout-seconds 20
    if ($LASTEXITCODE -ne 0) { throw 'Mock UI did not open.' }
    & npx.cmd playwright test --reporter=line
    if ($LASTEXITCODE -ne 0) { throw 'Playwright G02/G15/G25 failed.' }
} finally {
    if ($null -ne $uiJob) {
        Stop-Job $uiJob -ErrorAction SilentlyContinue
        Remove-Job $uiJob -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}

$env:APP_ENV = 'verify-mock'
$env:APP_DATABASE_URL = 'sqlite:///' + ((Join-Path $verifyDir 'chatbi.db') -replace '\\', '/')
$env:APP_ARTIFACT_DIR = Join-Path $verifyDir 'artifacts'
$env:APP_CHECKPOINT_PATH = Join-Path $verifyDir 'checkpoints.db'
$env:CHATBI_SEMANTIC_PACKAGE_DIR = Join-Path $verifyDir 'compiled-semantic'
$env:CHATBI_LLM_MODE = 'rule_based'
$env:CHATBI_GATEWAY_MODE = 'mock'
$backendJob = $null
try {
    $backendEnvironment = @{
        APP_ENV = $env:APP_ENV
        APP_DATABASE_URL = $env:APP_DATABASE_URL
        APP_ARTIFACT_DIR = $env:APP_ARTIFACT_DIR
        APP_CHECKPOINT_PATH = $env:APP_CHECKPOINT_PATH
        CHATBI_SEMANTIC_PACKAGE_DIR = $env:CHATBI_SEMANTIC_PACKAGE_DIR
        CHATBI_LLM_MODE = $env:CHATBI_LLM_MODE
        CHATBI_GATEWAY_MODE = $env:CHATBI_GATEWAY_MODE
    }
    $backendJob = Start-Job -ScriptBlock {
        param($Python, $WorkingDirectory, $Environment, $Stdout, $Stderr)
        foreach ($item in $Environment.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($item.Key, [string]$item.Value, 'Process')
        }
        Set-Location $WorkingDirectory
        & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 18000 1>$Stdout 2>$Stderr
    } -ArgumentList `
        (Join-Path $backendDir '.venv\Scripts\python.exe'), $backendDir, $backendEnvironment, `
        (Join-Path $verifyDir 'backend.stdout.log'), (Join-Path $verifyDir 'backend.stderr.log')
    & uv run --project $backendDir python (Join-Path $projectRoot 'scripts\wait_http.py') `
        'http://127.0.0.1:18000/api/v1/health/ready' --timeout-seconds 30
    if ($LASTEXITCODE -ne 0) { throw 'Mock backend readiness failed.' }
} finally {
    if ($null -ne $backendJob) {
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'PACKAGE VERIFICATION PASSED: lockfiles, Semantic, backend, frontend, G01-G25, Playwright, and Mock readiness.'
