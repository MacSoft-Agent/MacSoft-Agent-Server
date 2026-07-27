[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $root 'hermes\venv\Scripts\python.exe'
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'hermes\venv is missing. Run scripts\bootstrap-development.ps1 first.'
}
if (-not $npm) {
    throw 'Node.js and npm are missing. Run scripts\bootstrap-development.ps1 first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $root 'hermes\node_modules') -PathType Container)) {
    throw 'hermes\node_modules is missing. Run scripts\bootstrap-development.ps1 first.'
}

& (Join-Path $root 'scripts\check-repository-cleanliness.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'Repository cleanliness verification failed.'
}

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$(Join-Path $root 'product_runtime');$(Join-Path $root 'server')"

    Push-Location $root
    try {
        & $python -m unittest discover product_runtime\tests
        if ($LASTEXITCODE -ne 0) {
            throw 'Product-runtime tests failed.'
        }

        & $python -m unittest discover server\tests
        if ($LASTEXITCODE -ne 0) {
            throw 'Server tests failed.'
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $previousPythonPath
    }
}

Push-Location (Join-Path $root 'hermes')
try {
    & $npm.Source run test:baseline --workspace apps/desktop
    if ($LASTEXITCODE -ne 0) {
        throw 'Desktop baseline verification failed.'
    }
}
finally {
    Pop-Location
}

& (Join-Path $root 'scripts\check-repository-cleanliness.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'Post-test repository cleanliness verification failed.'
}

& git -C $root diff --check
if ($LASTEXITCODE -ne 0) {
    throw 'git diff --check failed.'
}

Write-Host 'Contributor verification passed.'
