param(
    [string]$Python
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $ProjectRoot "hermes\venv\Scripts\python.exe"
}
$Requirements = Join-Path $ProjectRoot "server\requirements.txt"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Hermes Python environment is missing. Set up hermes\venv before building the product runtime."
}
if (-not (Test-Path -LiteralPath $Requirements -PathType Leaf)) {
    throw "Server requirements are missing: $Requirements"
}

Write-Host "Synchronizing MacSoft Server dependencies into the packaged Hermes Python environment..."
& $Python -m pip install --disable-pip-version-check -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install MacSoft Server runtime dependencies into hermes\venv."
}

& $Python -c "import fastapi, multipart, openpyxl, pypdf, uvicorn, yaml"
if ($LASTEXITCODE -ne 0) {
    throw "MacSoft Server runtime dependency verification failed."
}

Write-Host "MacSoft Server runtime dependencies are ready."
