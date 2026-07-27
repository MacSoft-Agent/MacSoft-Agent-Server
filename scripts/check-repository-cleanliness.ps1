[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root

try {
    & git rev-parse --is-inside-work-tree | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'MacSoft Agent repository was not found.'
    }

    $tracked = @(& git -c core.quotePath=false ls-files)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not read the Git index.'
    }

    $forbiddenPatterns = @(
        '^(backup|logs|release|runtime|staging|work)/',
        '(^|/)(node_modules|venv|\.venv|__pycache__)/',
        '\.(db|db-shm|db-wal|sqlite|sqlite3|log|pyc|pyo)$',
        '^server/initialization\.json$',
        '^server/(autocount-api-result|macsoft-hermes-bridge-input)\.txt$',
        '^hermes/apps/[^/]+/src/.+\.js$'
    )
    $violations = @(
        $tracked | Where-Object {
            $path = $_
            $forbiddenPatterns | Where-Object { $path -match $_ } | Select-Object -First 1
        }
    )

    $required = @(
        'product.json',
        'hermes/pyproject.toml',
        'hermes/uv.lock',
        'hermes/package-lock.json',
        'server/pyproject.toml',
        'server/uv.lock',
        'packaging/templates/protected-resources.json',
        'scripts/build-release.ps1'
    )
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })

    & git diff --check
    $diffCheckFailed = $LASTEXITCODE -ne 0

    if ($violations.Count -gt 0) {
        Write-Host 'Tracked generated or private artifacts:' -ForegroundColor Red
        $violations | ForEach-Object { Write-Host "  $_" }
    }
    if ($missing.Count -gt 0) {
        Write-Host 'Missing reproducible-build inputs:' -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "  $_" }
    }

    if ($violations.Count -gt 0 -or $missing.Count -gt 0 -or $diffCheckFailed) {
        throw 'Repository cleanliness check failed.'
    }

    Write-Host "Repository structure is clean. Tracked files: $($tracked.Count)" -ForegroundColor Green
    $status = @(& git status --short)
    if ($status.Count -gt 0) {
        Write-Host "Working tree contains $($status.Count) pending path changes; review them before release."
    } else {
        Write-Host 'Working tree is clean.'
    }
}
finally {
    Pop-Location
}
