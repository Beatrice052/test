param(
    [Parameter(Mandatory = $true)][string]$InputDir,
    [Parameter(Mandatory = $true)][string[]]$SuccessStatus,
    [Parameter(Mandatory = $true)][string[]]$FailureStatus,
    [string[]]$PendingStatus = @(),
    [string[]]$UnknownStatus = @(),
    [Parameter(Mandatory = $true)][ValidateSet('success','failure','pending','unknown')][string]$NullGroup,
    [Parameter(Mandatory = $true)][int]$MinimumDenominator,
    [Parameter(Mandatory = $true)][string]$Owner
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    'run', '--project', (Join-Path $projectRoot 'backend'), 'python',
    (Join-Path $PSScriptRoot 'configure_failure_rate.py'),
    '--input-dir', $InputDir, '--null-group', $NullGroup,
    '--minimum-denominator', [string]$MinimumDenominator, '--owner', $Owner
)
foreach ($value in $SuccessStatus) { $arguments += @('--success-status', $value) }
foreach ($value in $FailureStatus) { $arguments += @('--failure-status', $value) }
foreach ($value in $PendingStatus) { $arguments += @('--pending-status', $value) }
foreach ($value in $UnknownStatus) { $arguments += @('--unknown-status', $value) }
& uv @arguments
exit $LASTEXITCODE
