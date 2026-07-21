$ErrorActionPreference = 'SilentlyContinue'

$deadline = [DateTime]::UtcNow.AddSeconds(150)
$lastState = 'Waiting for MacSoft Agent Host.'

while ([DateTime]::UtcNow -lt $deadline) {
    $service = Get-Service -Name 'MacSoftAgentHost' -ErrorAction SilentlyContinue
    if (-not $service -or $service.Status -ne 'Running') {
        $lastState = 'MacSoftAgentHost is not running.'
        Start-Sleep -Seconds 1
        continue
    }

    $aiHealthy = $false
    $serverHealthy = $false
    $controlHealthy = $false

    try {
        $ai = Invoke-RestMethod -Uri 'http://127.0.0.1:8642/health' -Method Get -TimeoutSec 3
        $aiHealthy = $ai.status -eq 'ok'
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

    if ($aiHealthy -and $serverHealthy -and $controlHealthy) {
        Write-Output 'MacSoft Agent Host, AI Service, and MacSoft Server are healthy.'
        exit 0
    }

    Start-Sleep -Seconds 1
}

Write-Error $lastState
exit 10
