[CmdletBinding()]
param(
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$StatePath = Join-Path $ProjectRoot 'server\data\host\test-runtime.json'
$OwnedPorts = @(8766, 8643, 8642, 8787, 5174)

function Get-ProcessRecord {
    param([int]$ProcessId)

    Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Get-DescendantProcessIds {
    param([int]$RootProcessId)

    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $result = New-Object 'System.Collections.Generic.HashSet[int]'
    $queue = New-Object 'System.Collections.Generic.Queue[int]'
    $queue.Enqueue($RootProcessId)
    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        foreach ($process in $all | Where-Object { [int]$_.ParentProcessId -eq $parent }) {
            $childId = [int]$process.ProcessId
            if ($result.Add($childId)) {
                $queue.Enqueue($childId)
            }
        }
    }
    return @($result)
}

function Stop-RecordedProcessTree {
    param(
        [int]$ProcessId,
        [string]$RequiredCommandText,
        [string]$Label
    )

    if ($ProcessId -le 0) {
        return
    }
    $record = Get-ProcessRecord -ProcessId $ProcessId
    if (-not $record) {
        return
    }
    $commandLine = ([string]$record.CommandLine).ToLowerInvariant()
    if (-not $commandLine.Contains($RequiredCommandText.ToLowerInvariant())) {
        throw "Refusing to stop PID $ProcessId because it is not the recorded $Label."
    }
    $descendants = @(Get-DescendantProcessIds -RootProcessId $ProcessId)
    foreach ($childId in ($descendants | Sort-Object -Descending)) {
        Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
    if (-not $Quiet) {
        Write-Host 'No MacSoft Agent test runtime launcher state was found.'
    }
    return
}

$state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
$desktopProcessId = [int]$state.desktop_pid
if ($desktopProcessId -gt 0) {
    Stop-RecordedProcessTree -ProcessId $desktopProcessId -RequiredCommandText 'dev:macsoft' -Label 'MacSoft Agent test Desktop launcher'
}

$recordedProcessId = [int]$state.pid
$hostProcess = Get-ProcessRecord -ProcessId $recordedProcessId
if ($hostProcess) {
    $expectedRoot = $ProjectRoot.ToLowerInvariant()
    $commandLine = ([string]$hostProcess.CommandLine).ToLowerInvariant()
    if (-not $commandLine.Contains('product_runtime.macsoft_runtime.cli') -or -not $commandLine.Contains($expectedRoot)) {
        throw "Refusing to stop PID $recordedProcessId because it is not the recorded MacSoft Agent test Host."
    }

    Stop-RecordedProcessTree -ProcessId $recordedProcessId -RequiredCommandText 'product_runtime.macsoft_runtime.cli' -Label 'MacSoft Agent test Host'
}

$deadline = [DateTime]::UtcNow.AddSeconds(15)
do {
    $listeners = @(
        Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $OwnedPorts -contains $_.LocalPort }
    )
    if ($listeners.Count -eq 0) {
        break
    }
    Start-Sleep -Milliseconds 250
} while ([DateTime]::UtcNow -lt $deadline)

if ($listeners.Count -gt 0) {
    $summary = ($listeners | ForEach-Object { "$($_.LocalPort):$($_.OwningProcess)" }) -join ', '
    throw "The recorded test Host stopped, but runtime listeners remain: $summary"
}

Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
if (-not $Quiet) {
    Write-Host 'MacSoft Agent test runtime and Desktop stopped. Ports 8766, 8643, 8642, 8787, and 5174 are released.'
}
