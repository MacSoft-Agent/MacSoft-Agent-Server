param(
    [Parameter(Mandatory = $true)]
    [string]$ProgramRoot
)

$ErrorActionPreference = 'SilentlyContinue'

$deadline = [DateTime]::UtcNow.AddSeconds(150)
$lastState = 'Waiting for MacSoft Agent Host.'
$product = Get-Content -LiteralPath (Join-Path $ProgramRoot 'product.json') -Raw |
    ConvertFrom-Json

while ([DateTime]::UtcNow -lt $deadline) {
    $service = Get-Service -Name 'MacSoftAgentHost' -ErrorAction SilentlyContinue
    if (-not $service -or $service.Status -ne 'Running') {
        $lastState = 'MacSoftAgentHost is not running.'
        Start-Sleep -Seconds 1
        continue
    }

    $aiHealthy = $false
    $serverHealthy = $false
    $configHealthy = $false
    $controlHealthy = $false

    try {
        $config = Invoke-RestMethod -Uri 'http://127.0.0.1:8643/api/status' -Method Get -TimeoutSec 3
        $configHealthy = $config.runtime_mode -eq 'config-only'
        if (-not $configHealthy) {
            $lastState = 'Configuration backend identity check failed.'
        }
    } catch {
        $lastState = 'Configuration backend health is not ready.'
    }

    try {
        $ai = Invoke-RestMethod -Uri 'http://127.0.0.1:8642/health' -Method Get -TimeoutSec 3
        $runtime = $ai.macsoft_runtime
        $aiHealthy = [bool](
            $ai.status -eq 'ok' -and
            $ai.platform -eq 'hermes-agent' -and
            $runtime.runtime -eq 'hermes-agent' -and
            $runtime.runtime_base_version -eq $product.runtime_base_version -and
            $runtime.runtime_base_commit -eq $product.runtime_base_commit -and
            $runtime.runtime_contract_version -eq $product.runtime_contract_version -and
            $runtime.runtime_metadata_schema_version -eq $product.runtime_metadata_schema_version
        )
        if (-not $aiHealthy) {
            $lastState = 'AI Service runtime compatibility handshake failed.'
        }
    } catch {
        $lastState = 'AI Service health is not ready.'
    }

    try {
        $server = Invoke-RestMethod -Uri 'http://127.0.0.1:8787/health' -Method Get -TimeoutSec 3
        $serverHealthy = $server.ok -eq $true -and $server.server -eq 'MacSoft Server'
    } catch {
        $lastState = 'MacSoft Server health is not ready.'
    }

    $controlHealthy = [bool](
        Get-NetTCPConnection -State Listen -LocalPort 8766 -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalAddress -in @('127.0.0.1', '::1') } |
            Select-Object -First 1
    )
    if (-not $controlHealthy) {
        $lastState = 'Host control endpoint is not ready.'
    }

    if ($configHealthy -and $aiHealthy -and $serverHealthy -and $controlHealthy) {
        Write-Output 'MacSoft Agent Host, configuration backend, AI Service, and MacSoft Server are healthy.'
        exit 0
    }

    Start-Sleep -Seconds 1
}

Write-Error $lastState
exit 10
