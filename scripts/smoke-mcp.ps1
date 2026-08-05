param(
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Dataset,
    [Parameter(Mandatory = $true)][string[]]$Index,
    [Parameter(Mandatory = $true)][string]$TimeField,
    [Parameter(Mandatory = $true)][string[]]$DimensionField,
    [Parameter(Mandatory = $true)][string]$From,
    [Parameter(Mandatory = $true)][string]$To,
    [Parameter(Mandatory = $true)][string]$Output,
    [string]$Timezone = 'Asia/Hong_Kong'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    'run', '--project', (Join-Path $projectRoot 'backend'), 'python', '-m', 'app.cli',
    'mcp', 'smoke', '--config', $Config, '--dataset', $Dataset,
    '--time-field', $TimeField,
    '--from', $From, '--to', $To, '--timezone', $Timezone, '--output', $Output
)
foreach ($value in $Index) { $arguments += @('--index', $value) }
foreach ($value in $DimensionField) { $arguments += @('--dimension-field', $value) }
& uv @arguments
exit $LASTEXITCODE
