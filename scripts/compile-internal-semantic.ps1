param(
    [Parameter(Mandatory = $true)][string]$InputDir,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [string]$Profile = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    'run', '--project', (Join-Path $projectRoot 'backend'), 'python', '-m', 'app.cli',
    'semantic', 'compile', '--input-dir', $InputDir, '--output-dir', $OutputDir
)
if ($Profile) { $arguments += @('--profile', $Profile) }
& uv @arguments
exit $LASTEXITCODE
