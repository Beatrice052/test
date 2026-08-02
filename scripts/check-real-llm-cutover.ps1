param([string]$Output = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @('run', '--project', (Join-Path $projectRoot 'backend'), 'python', '-m', 'app.cli', 'llm', 'cutover-check')
if ($Output) { $arguments += @('--output', $Output) }
& uv @arguments
exit $LASTEXITCODE
