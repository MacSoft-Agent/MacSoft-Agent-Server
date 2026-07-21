param(
    [string]$Output = "C:\MacSoft-Agent\staging\MacSoft-Agent-0.1.0",
    [string]$DesktopDirectory = "C:\MacSoft-Agent\hermes\apps\desktop\release\win-unpacked"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot "hermes\venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "product_runtime"

& $Python -m macsoft_runtime.staging `
    --source-root $ProjectRoot `
    --desktop-dir $DesktopDirectory `
    --output $Output

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
