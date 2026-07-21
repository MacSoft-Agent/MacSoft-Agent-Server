[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$runtime = Join-Path $ProjectRoot "runtime"
$output = Join-Path $ProjectRoot "docs\hermes-runtime-inventory.csv"

if (-not (Test-Path -LiteralPath $runtime)) {
    throw "Runtime directory not found: $runtime"
}

$rows = Get-ChildItem -Force -LiteralPath $runtime -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($runtime.Length).TrimStart("\")
    [pscustomobject]@{
        RelativePath = $relative
        Type = if ($_.PSIsContainer) { "Directory" } else { "File" }
        Bytes = if ($_.PSIsContainer) { $null } else { $_.Length }
        LastWriteTimeUtc = $_.LastWriteTimeUtc.ToString("o")
    }
}

$rows | Sort-Object RelativePath | Export-Csv -LiteralPath $output -NoTypeInformation -Encoding utf8
Write-Host "Runtime inventory written to $output"
