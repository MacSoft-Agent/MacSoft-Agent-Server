[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ports = 8642, 8787

foreach ($port in $ports) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping $($process.ProcessName) PID $($process.Id) on port $port"
            Stop-Process -Id $process.Id -Force
        }
    }
}

Start-Sleep -Seconds 2

$remaining = foreach ($port in $ports) {
    Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
}

if ($remaining) {
    throw "One or more runtime ports are still listening."
}

Write-Host "MacSoft Agent AI Service and MacSoft Server ports are stopped."
