param(
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Dataset,
    [Parameter(Mandatory = $true)][string[]]$Index,
    [Parameter(Mandatory = $true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    'run', '--project', (Join-Path $projectRoot 'backend'), 'python', '-m', 'app.cli',
    'semantic', 'snapshot-mapping', '--config', $Config, '--dataset', $Dataset, '--output', $Output
)
foreach ($value in $Index) { $arguments += @('--index', $value) }
& uv @arguments
exit $LASTEXITCODE
