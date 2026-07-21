param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$NsisPath
)

$ErrorActionPreference = 'Stop'

$payload = [IO.Path]::GetFullPath($PayloadRoot)
$output = [IO.Path]::GetFullPath($OutputPath)
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installerScript = Join-Path $scriptRoot 'installer\MacSoft-Agent.nsi'
$manifestPath = Join-Path $payload 'staging-manifest.json'

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "The staging manifest was not found under $payload."
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$expected = @{}
foreach ($entry in $manifest.files) {
    $expected[[string]$entry.path] = $entry
}

$actual = @{}
Get-ChildItem -LiteralPath $payload -Recurse -File |
    Where-Object { $_.FullName -ne $manifestPath } |
    ForEach-Object {
        $relative = $_.FullName.Substring($payload.Length + 1).Replace('\', '/')
        $actual[$relative] = $_
    }

$missing = @($expected.Keys | Where-Object { -not $actual.ContainsKey($_) })
$extra = @($actual.Keys | Where-Object { -not $expected.ContainsKey($_) })
if ($missing.Count -or $extra.Count) {
    throw "The payload does not match its manifest. Missing=$($missing.Count) Extra=$($extra.Count)."
}

foreach ($relative in $expected.Keys) {
    $entry = $expected[$relative]
    $file = $actual[$relative]
    if ($file.Length -ne [int64]$entry.bytes) {
        throw "Payload size mismatch: $relative"
    }
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne ([string]$entry.sha256).ToLowerInvariant()) {
        throw "Payload hash mismatch: $relative"
    }
}

if (-not $NsisPath) {
    $cacheRoot = Join-Path $env:LOCALAPPDATA 'electron-builder\Cache'
    $NsisPath = Get-ChildItem -LiteralPath $cacheRoot -Recurse -File -Filter makensis.exe |
        Where-Object { $_.DirectoryName -notmatch '\\Bin$' } |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $NsisPath -or -not (Test-Path -LiteralPath $NsisPath -PathType Leaf)) {
    throw 'makensis.exe could not be located.'
}

$outputDirectory = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Force
}

& $NsisPath "/DPAYLOAD_ROOT=$payload" "/DOUTPUT_FILE=$output" '/DPRODUCT_VERSION=0.1.0' $installerScript
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "NSIS failed with exit code $LASTEXITCODE."
}

$result = Get-Item -LiteralPath $output
[pscustomobject]@{
    Installer = $result.FullName
    Bytes = $result.Length
    Sha256 = (Get-FileHash -LiteralPath $result.FullName -Algorithm SHA256).Hash
    PayloadFiles = $expected.Count
}
