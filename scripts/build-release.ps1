[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit,

    [string]$NsisPath
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
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
$installerArguments = @{
    PayloadRoot = $stagingPath
    OutputPath = $installerPath
}
if ($NsisPath) {
    $installerArguments.NsisPath = $NsisPath
}
$installer = & (Join-Path $ProjectRoot 'packaging\build-installer.ps1') @installerArguments

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
    installer_bytes = (Get-Item -LiteralPath $installerPath).Length
    installer_sha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
$reportPath = Join-Path $releaseDirectory 'build-report.json'
$report | ConvertTo-Json | Set-Content -LiteralPath $reportPath -Encoding utf8
$report
