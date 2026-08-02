param(
    [Parameter(Mandatory = $true)][string]$InputDir,
    [Parameter(Mandatory = $true)][string]$OutputDir
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& uv run --project (Join-Path $projectRoot 'backend') python -m app.cli semantic compile `
    --input-dir $InputDir --output-dir $OutputDir
exit $LASTEXITCODE
