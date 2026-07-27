[CmdletBinding()]
param(
    [string]$PythonVersion = '3.12.13'
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$required = @(
    'product.json',
    'hermes\pyproject.toml',
    'hermes\uv.lock',
    'hermes\package.json',
    'hermes\package-lock.json',
    'server\pyproject.toml',
    'server\uv.lock'
)

foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) {
        throw "Required development input is missing: $relative"
    }
}

$uv = Get-Command uv.exe -ErrorAction SilentlyContinue
if (-not $uv) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
}
if (-not $uv) {
    throw 'uv is required. Install uv 0.11.16 or newer, then rerun this script.'
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npm) {
    throw 'Node.js 24 and npm are required.'
}

$hermesRoot = Join-Path $root 'hermes'
$hermesVenv = Join-Path $hermesRoot 'venv'
$venvPython = Join-Path $hermesVenv 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    Write-Host "Creating the Python $PythonVersion development environment..."
    & $uv.Source venv $hermesVenv --python $PythonVersion
    if ($LASTEXITCODE -ne 0) {
        throw 'uv could not create hermes\venv.'
    }
}

Write-Host 'Synchronizing locked Python development dependencies...'
$previousEnvironment = $env:UV_PROJECT_ENVIRONMENT
try {
    $env:UV_PROJECT_ENVIRONMENT = $hermesVenv
    & $uv.Source sync --project $hermesRoot --extra dev --extra macsoft-server --locked
    if ($LASTEXITCODE -ne 0) {
        throw 'uv could not synchronize hermes\uv.lock.'
    }
}
finally {
    if ($null -eq $previousEnvironment) {
        Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
    }
    else {
        $env:UV_PROJECT_ENVIRONMENT = $previousEnvironment
    }
}

Write-Host 'Installing locked Node workspace dependencies...'
Push-Location $hermesRoot
try {
    & $npm.Source ci
    if ($LASTEXITCODE -ne 0) {
        throw 'npm ci failed for hermes\package-lock.json.'
    }
}
finally {
    Pop-Location
}

Write-Host 'Development dependencies are ready.'
