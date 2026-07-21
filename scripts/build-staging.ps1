param(
    [string]$Output,
    [string]$DesktopDirectory
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Output) {
    $Output = Join-Path $ProjectRoot "staging\MacSoft-Agent-0.1.0"
}
if (-not $DesktopDirectory) {
    $DesktopDirectory = Join-Path $ProjectRoot "hermes\apps\desktop\release\win-unpacked"
}
$Python = Join-Path $ProjectRoot "hermes\venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "product_runtime"

& (Join-Path $PSScriptRoot "sync-server-runtime-dependencies.ps1") -Python $Python
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python -m macsoft_runtime.staging `
    --source-root $ProjectRoot `
    --desktop-dir $DesktopDirectory `
    --output $Output

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
