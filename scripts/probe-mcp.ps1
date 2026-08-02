param(
    [Parameter(Mandatory = $true)][string]$Config,
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @('run', '--project', (Join-Path $projectRoot 'backend'), 'python', '-m', 'app.cli', 'mcp', 'probe', '--config', $Config)
if ($Output) { $arguments += @('--output', $Output) }
& uv @arguments
exit $LASTEXITCODE
