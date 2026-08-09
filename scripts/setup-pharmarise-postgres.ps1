[CmdletBinding()]
param(
    [string]$PostgresHost = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$PostgresPort = 5432,
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$AdminUser = 'postgres',
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$Database = 'macsoft_workflow',
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$ApplicationUser = 'macsoft_workflow_app',
    [string[]]$ConfigPath
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$migration = Join-Path $root 'packaging\templates\protected\runtime\plugins\macsoft-autocount\migrations\001_pharmarise_workflow.sql'
if (-not (Test-Path -LiteralPath $migration -PathType Leaf)) {
    throw "PharmaRise migration is missing: $migration"
}

if (-not $ConfigPath -or $ConfigPath.Count -eq 0) {
    $ConfigPath = @((Join-Path $root 'runtime\plugins\macsoft-autocount\config.json'))
}

$psql = Get-Command psql.exe -ErrorAction SilentlyContinue
if (-not $psql) {
    $psql = Get-ChildItem -LiteralPath (Join-Path $env:ProgramFiles 'PostgreSQL') `
        -Filter psql.exe -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
}
if (-not $psql) {
    throw 'PostgreSQL command-line tools are missing. Install PostgreSQL 17, then rerun this script.'
}
$psqlPath = if ($psql.Source) { [string]$psql.Source } else { [string]$psql.FullName }
$createdb = Join-Path (Split-Path -Parent $psqlPath) 'createdb.exe'
if (-not (Test-Path -LiteralPath $createdb -PathType Leaf)) {
    throw "createdb.exe is missing beside psql.exe: $createdb"
}

function ConvertFrom-SecureValue([Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

function Invoke-Psql([string[]]$Arguments, [string]$Password) {
    $previous = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $Password
        & $psqlPath @Arguments
        if ($LASTEXITCODE -ne 0) { throw "psql failed with exit code $LASTEXITCODE." }
    }
    finally {
        if ($null -eq $previous) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
        else { $env:PGPASSWORD = $previous }
    }
}

$adminSecure = Read-Host 'PostgreSQL administrator password' -AsSecureString
$adminPassword = ConvertFrom-SecureValue $adminSecure
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
try { $random.GetBytes($bytes) }
finally { $random.Dispose() }
$applicationPassword = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
$sqlPassword = $applicationPassword.Replace("'", "''")

try {
    $common = @('-h', $PostgresHost, '-p', [string]$PostgresPort, '-U', $AdminUser, '-d', 'postgres', '-v', 'ON_ERROR_STOP=1')
    $previous = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $adminPassword
        $roleExists = & $psqlPath @common '-tAc' "SELECT 1 FROM pg_roles WHERE rolname = '$ApplicationUser'"
        if ($LASTEXITCODE -ne 0) { throw 'Could not query PostgreSQL roles.' }
        $databaseExists = & $psqlPath @common '-tAc' "SELECT 1 FROM pg_database WHERE datname = '$Database'"
        if ($LASTEXITCODE -ne 0) { throw 'Could not query PostgreSQL databases.' }
    }
    finally {
        if ($null -eq $previous) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
        else { $env:PGPASSWORD = $previous }
    }

    if ([string]$roleExists -eq '1') {
        Invoke-Psql ($common + @('-c', "ALTER ROLE $ApplicationUser WITH LOGIN PASSWORD '$sqlPassword'")) $adminPassword
    }
    else {
        Invoke-Psql ($common + @('-c', "CREATE ROLE $ApplicationUser WITH LOGIN PASSWORD '$sqlPassword'")) $adminPassword
    }

    if ([string]$databaseExists -ne '1') {
        $previous = $env:PGPASSWORD
        try {
            $env:PGPASSWORD = $adminPassword
            & $createdb -h $PostgresHost -p $PostgresPort -U $AdminUser -O $ApplicationUser $Database
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the PharmaRise database.' }
        }
        finally {
            if ($null -eq $previous) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
            else { $env:PGPASSWORD = $previous }
        }
    }

    Invoke-Psql @('-h', $PostgresHost, '-p', [string]$PostgresPort, '-U', $ApplicationUser, '-d', $Database, '-v', 'ON_ERROR_STOP=1', '-f', $migration) $applicationPassword

    $encodedUser = [Uri]::EscapeDataString($ApplicationUser)
    $encodedPassword = [Uri]::EscapeDataString($applicationPassword)
    $dsn = "postgresql://${encodedUser}:${encodedPassword}@${PostgresHost}:${PostgresPort}/${Database}"
    foreach ($pathValue in $ConfigPath) {
        $resolved = [IO.Path]::GetFullPath($pathValue)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "AutoCount runtime config is missing: $resolved"
        }
        $config = Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
        $evidenceRoot = Join-Path (Split-Path -Parent (Split-Path -Parent $resolved)) 'workflow-evidence'
        New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
        $config | Add-Member -NotePropertyName workflowPostgresDsn -NotePropertyValue $dsn -Force
        $config | Add-Member -NotePropertyName workflowPostgresConnectTimeoutSeconds -NotePropertyValue 10 -Force
        $config | Add-Member -NotePropertyName workflowEvidenceRoot -NotePropertyValue $evidenceRoot -Force
        $temporary = "$resolved.tmp"
        $config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $temporary -Encoding utf8
        Move-Item -LiteralPath $temporary -Destination $resolved -Force
    }
}
finally {
    $adminPassword = $null
    $applicationPassword = $null
    $sqlPassword = $null
}

Write-Host "PharmaRise PostgreSQL is ready: $PostgresHost`:$PostgresPort/$Database"
Write-Host 'The application DSN was written only to the selected local runtime config file(s).'
