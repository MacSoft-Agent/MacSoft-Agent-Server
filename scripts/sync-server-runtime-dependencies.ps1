param(
    [string]$Python,
    [string]$Uv,
    [switch]$IncludeDev
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $ProjectRoot "hermes\venv\Scripts\python.exe"
}
$HermesProject = Join-Path $ProjectRoot "hermes"
$HermesLock = Join-Path $HermesProject "uv.lock"

if (-not $Uv) {
    $UvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($UvCommand) {
        $Uv = $UvCommand.Source
    }
}
if (-not $Uv -and $env:LOCALAPPDATA) {
    $WinGetPackages = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $Uv = Get-ChildItem -LiteralPath $WinGetPackages -Directory -Filter "astral-sh.uv_*" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -File -Filter "uv.exe" -ErrorAction SilentlyContinue } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Hermes Python environment is missing. Set up hermes\venv before building the product runtime."
}
if (-not (Test-Path -LiteralPath $HermesLock -PathType Leaf)) {
    throw "Unified product uv lock is missing: $HermesLock"
}
if (-not $Uv -or -not (Test-Path -LiteralPath $Uv -PathType Leaf)) {
    throw "uv is unavailable. Install uv or pass its executable path with -Uv."
}

Write-Host "Synchronizing Hermes and MacSoft Server from the unified product uv lock..."
$previousEnvironment = $env:UV_PROJECT_ENVIRONMENT
try {
    $env:UV_PROJECT_ENVIRONMENT = [IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $Python)))
    $syncArguments = @('sync', '--project', $HermesProject, '--extra', 'all', '--locked')
    if ($IncludeDev) {
        $syncArguments += @('--extra', 'dev')
    }
    & $Uv @syncArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to synchronize the unified Hermes and MacSoft Server runtime environment."
    }
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $previousEnvironment
}

& $Python -c "import fastapi, multipart, openpyxl, pypdf, uvicorn, yaml"
if ($LASTEXITCODE -ne 0) {
    throw "MacSoft Server runtime dependency verification failed."
}

Write-Host "Hermes and MacSoft Server runtime dependencies are ready."
