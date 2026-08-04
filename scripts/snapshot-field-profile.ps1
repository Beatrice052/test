param(
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Dataset,
    [Parameter(Mandatory = $true)][string]$Mapping,
    [Parameter(Mandatory = $true)][string]$SemanticPackage,
    [Parameter(Mandatory = $true)][string]$Output,
    [int]$MaxFields = 100,
    [int]$SampleValueLimit = 5
)

$projectRoot = Split-Path -Parent $PSScriptRoot
uv run --project (Join-Path $projectRoot 'backend') python -m app.cli semantic snapshot-profile `
    --config $Config `
    --dataset $Dataset `
    --mapping $Mapping `
    --semantic-package $SemanticPackage `
    --max-fields $MaxFields `
    --sample-value-limit $SampleValueLimit `
    --output $Output
exit $LASTEXITCODE
