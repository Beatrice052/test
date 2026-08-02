param(
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& uv run --project (Join-Path $projectRoot 'backend') python `
    (Join-Path $PSScriptRoot 'build_shadow_report.py') @Arguments
exit $LASTEXITCODE
