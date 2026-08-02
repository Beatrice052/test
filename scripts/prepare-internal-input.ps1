param(
    [Parameter(Mandatory = $true)][string]$FieldCatalog,
    [Parameter(Mandatory = $true)][string]$Mapping,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [string]$IndexPattern = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    'run', '--project', (Join-Path $projectRoot 'backend'), 'python',
    (Join-Path $PSScriptRoot 'prepare_internal_input.py'),
    '--field-catalog', $FieldCatalog, '--mapping', $Mapping, '--output-dir', $OutputDir
)
if ($IndexPattern) { $arguments += @('--index-pattern', $IndexPattern) }
& uv @arguments
exit $LASTEXITCODE
