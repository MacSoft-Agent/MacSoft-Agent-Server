[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit,

    [string]$NsisPath,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Production', 'InternalTestUnsigned')]
    [string]$ArtifactMode,

    [string]$SigningCommandPath,

    [string]$SignToolPath
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if ($ArtifactMode -eq 'Production' -and -not $SigningCommandPath) {
    throw 'Production release builds require an external signing command.'
}
if ($ArtifactMode -eq 'InternalTestUnsigned' -and $SigningCommandPath) {
    throw 'InternalTestUnsigned builds do not accept a signing command.'
}
if ((Split-Path -Leaf $ProjectRoot) -ne 'MacSoft-Agent-Packaging') {
    throw 'Release builds are allowed only from the MacSoft-Agent-Packaging clone.'
}

$requiredMarkers = @('product.json', '.git', 'hermes\uv.lock', 'hermes\package-lock.json', 'server\uv.lock', 'packaging\installer\MacSoft-Agent.nsi')
foreach ($relative in $requiredMarkers) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $relative))) {
        throw "Packaging source marker is missing: $relative"
    }
}

$head = (& git -C $ProjectRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedCommit.ToLowerInvariant()) {
    throw "Packaging HEAD $head does not match the accepted commit $ExpectedCommit."
}
$dirty = @(& git -C $ProjectRoot status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -gt 0) {
    throw 'Packaging source must be a clean Git clone before building.'
}

$ownedPorts = @(8766, 8643, 8642, 8787, 5174)
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ownedPorts -contains $_.LocalPort })
if ($listeners.Count -gt 0) {
    $summary = ($listeners | ForEach-Object { "$($_.LocalPort):$($_.OwningProcess)" }) -join ', '
    throw "Stop the development test runtime before packaging. Active listeners: $summary"
}

$UvCommand = Get-Command uv.exe -ErrorAction Stop
$NpmCommand = Get-Command npm.cmd -ErrorAction Stop
$Product = Get-Content -LiteralPath (Join-Path $ProjectRoot 'product.json') -Raw | ConvertFrom-Json
$HermesVenv = Join-Path $ProjectRoot 'hermes\venv'

Write-Host "Creating the clean Python 3.12.13 product environment..."
& $UvCommand.Source venv $HermesVenv --python 3.12.13 --clear
if ($LASTEXITCODE -ne 0) {
    throw 'uv could not create hermes\venv.'
}
$previousEnvironment = $env:UV_PROJECT_ENVIRONMENT
try {
    $env:UV_PROJECT_ENVIRONMENT = $HermesVenv
    & $UvCommand.Source sync --project (Join-Path $ProjectRoot 'hermes') --extra all --locked
    if ($LASTEXITCODE -ne 0) {
        throw 'uv could not synchronize the unified product lock.'
    }
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $previousEnvironment
}

Write-Host 'Installing the locked Desktop workspace dependencies...'
Push-Location (Join-Path $ProjectRoot 'hermes')
try {
    & $NpmCommand.Source ci
    if ($LASTEXITCODE -ne 0) {
        throw 'npm ci failed.'
    }
    & $NpmCommand.Source run pack --workspace apps/desktop
    if ($LASTEXITCODE -ne 0) {
        throw 'Electron win-unpacked build failed.'
    }
} finally {
    Pop-Location
}

$stagingName = "MacSoft-Agent-$($Product.product_version)-$($Product.build_id)"
$stagingPath = Join-Path $ProjectRoot "staging\$stagingName"
if (Test-Path -LiteralPath $stagingPath) {
    throw "Release staging must be new and empty: $stagingPath"
}
& (Join-Path $PSScriptRoot 'build-staging.ps1') -Output $stagingPath
if ($LASTEXITCODE -ne 0) {
    throw 'Product staging failed.'
}

$releaseDirectory = Join-Path $ProjectRoot 'release'
$installerPath = Join-Path $releaseDirectory "MacSoft-Agent-Setup-$($Product.product_version).exe"
$reportPath = Join-Path $releaseDirectory 'build-report.json'
if (Test-Path -LiteralPath $reportPath) {
    Remove-Item -LiteralPath $reportPath -Force
}
$installerArguments = @{
    PayloadRoot = $stagingPath
    OutputPath = $installerPath
}
if ($NsisPath) {
    $installerArguments.NsisPath = $NsisPath
}
$installer = & (Join-Path $ProjectRoot 'packaging\build-installer.ps1') @installerArguments

$finalizationArguments = @{
    InstallerPath = $installerPath
    ArtifactMode = $ArtifactMode
}
if ($SigningCommandPath) {
    $finalizationArguments.SigningCommandPath = $SigningCommandPath
}
if ($SignToolPath) {
    $finalizationArguments.SignToolPath = $SignToolPath
}
$artifact = & (Join-Path $PSScriptRoot 'finalize-release-artifact.ps1') @finalizationArguments

$manifestPath = Join-Path $stagingPath 'staging-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$report = [ordered]@{
    product = $Product.product
    product_version = $Product.product_version
    build_id = $Product.build_id
    git_commit = $head
    built_at = [DateTime]::UtcNow.ToString('o')
    desktop = Join-Path $ProjectRoot 'hermes\apps\desktop\release\win-unpacked'
    staging = $stagingPath
    staging_files = @($manifest.files).Count
    staging_manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    installer = $installerPath
    artifact_class = $artifact.artifact_class
    production_ready = $artifact.production_ready
    authenticode_status = $artifact.authenticode_status
    timestamped = $artifact.timestamped
    rfc3161_verified = $artifact.rfc3161_verified
    timestamp_digest_algorithm = $artifact.timestamp_digest_algorithm
    signer_subject = $artifact.signer_subject
    signer_thumbprint = $artifact.signer_thumbprint
    timestamp_subject = $artifact.timestamp_subject
    timestamp_thumbprint = $artifact.timestamp_thumbprint
    installer_bytes = $artifact.installer_bytes
    installer_sha256 = $artifact.installer_sha256
}
$reportTemporaryPath = "$reportPath.$([Guid]::NewGuid().ToString('N')).tmp"
try {
    $report | ConvertTo-Json | Set-Content -LiteralPath $reportTemporaryPath -Encoding utf8
    $writtenReport = Get-Content -LiteralPath $reportTemporaryPath -Raw | ConvertFrom-Json
    if (
        [int64]$writtenReport.installer_bytes -ne [int64]$artifact.installer_bytes -or
        [string]$writtenReport.installer_sha256 -ne [string]$artifact.installer_sha256 -or
        [bool]$writtenReport.production_ready -ne [bool]$artifact.production_ready -or
        [bool]$writtenReport.rfc3161_verified -ne [bool]$artifact.rfc3161_verified -or
        [string]$writtenReport.timestamp_digest_algorithm -ne
            [string]$artifact.timestamp_digest_algorithm
    ) {
        throw 'The final build report does not match the finalized installer evidence.'
    }
    Move-Item -LiteralPath $reportTemporaryPath -Destination $reportPath
}
finally {
    Remove-Item -LiteralPath $reportTemporaryPath -Force -ErrorAction SilentlyContinue
}
$report
