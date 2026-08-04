param(
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Dataset,
    [string[]]$Index,
    [string]$IndexPattern,
    [Parameter(Mandatory = $true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    'run', '--project', (Join-Path $projectRoot 'backend'), 'python', '-m', 'app.cli',
    'semantic', 'snapshot-mapping', '--config', $Config, '--dataset', $Dataset, '--output', $Output
)
if ($IndexPattern) {
    $arguments += @('--index-pattern', $IndexPattern)
} elseif ($Index) {
    foreach ($value in $Index) { $arguments += @('--index', $value) }
} else {
    throw 'Provide -Index or -IndexPattern.'
}
& uv @arguments
exit $LASTEXITCODE
