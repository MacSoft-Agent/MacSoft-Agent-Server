param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('PreInstall', 'Cleanup')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$ProgramRoot,

    [Parameter(Mandatory = $true)]
    [string]$DataRoot,

    [ValidateSet(0, 1)]
    [int]$PurgeData = 0
)

$ErrorActionPreference = 'Stop'
$serviceName = 'MacSoftAgentHost'
$firewallRule = 'MacSoft Agent Server 8787'
$script:RebootRequired = $false

function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [int[]]$AllowedExitCodes = @(0)
    )

    & $FilePath @Arguments | Out-Host
    $exitCode = $LASTEXITCODE
    if ($exitCode -notin $AllowedExitCodes) {
        throw "$([IO.Path]::GetFileName($FilePath)) failed with exit code $exitCode."
    }
    return $exitCode
}

function Get-ServiceRecord {
    Get-CimInstance Win32_Service -Filter "Name='$serviceName'" -ErrorAction SilentlyContinue
}

function Get-DescendantProcessIds {
    param([int]$RootProcessId)

    if ($RootProcessId -le 0) {
        return @()
    }
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $result = New-Object 'System.Collections.Generic.HashSet[int]'
    $queue = New-Object 'System.Collections.Generic.Queue[int]'
    $queue.Enqueue($RootProcessId)
    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        foreach ($process in $all | Where-Object { [int]$_.ParentProcessId -eq $parent }) {
            $childProcessId = [int]$process.ProcessId
            if ($result.Add($childProcessId)) {
                $queue.Enqueue($childProcessId)
            }
        }
    }
    return @($result)
}

function Get-NormalizedProgramRoot {
    $trimCharacters = [char[]]@(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    return [IO.Path]::GetFullPath($ProgramRoot).TrimEnd($trimCharacters)
}

function Get-InstalledProgramProcesses {
    if (-not (Test-Path -LiteralPath $ProgramRoot -PathType Container)) {
        return @()
    }

    $normalizedRoot = Get-NormalizedProgramRoot
    $rootPrefix = $normalizedRoot + [IO.Path]::DirectorySeparatorChar
    $ownedProcesses = @()
    foreach ($process in @(Get-CimInstance Win32_Process -ErrorAction Stop)) {
        $executablePath = [string]$process.ExecutablePath
        if ([string]::IsNullOrWhiteSpace($executablePath)) {
            continue
        }
        try {
            $normalizedExecutable = [IO.Path]::GetFullPath($executablePath)
        } catch {
            continue
        }
        if ($normalizedExecutable.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            $ownedProcesses += $process
        }
    }
    return @($ownedProcesses)
}

function Stop-InstalledProgramProcesses {
    $ownedProcesses = @(Get-InstalledProgramProcesses)
    foreach ($ownedProcess in $ownedProcesses) {
        $process = Get-Process -Id ([int]$ownedProcess.ProcessId) -ErrorAction SilentlyContinue
        if ($process -and $process.MainWindowHandle -ne 0) {
            [void]$process.CloseMainWindow()
        }
    }

    $gracefulDeadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $remaining = @(Get-InstalledProgramProcesses)
        if ($remaining.Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $gracefulDeadline)

    foreach ($remainingProcess in $remaining) {
        $remainingProcessId = [int]$remainingProcess.ProcessId
        $process = Get-Process -Id $remainingProcessId -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $remainingProcessId -Force -ErrorAction Stop
        }
    }

    $forcedDeadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $remaining = @(Get-InstalledProgramProcesses)
        if ($remaining.Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $forcedDeadline)

    $remainingIds = ($remaining | ForEach-Object { [int]$_.ProcessId }) -join ', '
    throw "MacSoft Agent processes remain active under $ProgramRoot. Process IDs: $remainingIds"
}

function Stop-OwnedServiceTree {
    $service = Get-ServiceRecord
    if (-not $service) {
        return
    }

    $ownedChildren = @(Get-DescendantProcessIds -RootProcessId ([int]$service.ProcessId))
    if ($service.State -ne 'Stopped') {
        Invoke-Native -FilePath "$env:SystemRoot\System32\sc.exe" -Arguments @('stop', $serviceName) -AllowedExitCodes @(0, 1060, 1062) | Out-Null
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $service = Get-ServiceRecord
    } while ($service -and $service.State -ne 'Stopped' -and [DateTime]::UtcNow -lt $deadline)

    if ($service -and $service.State -ne 'Stopped') {
        throw "The $serviceName service did not stop within 30 seconds."
    }

    foreach ($processId in $ownedChildren) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            $process.WaitForExit(5000)
        }
    }
}

function Remove-ServiceChecked {
    if (-not (Get-ServiceRecord)) {
        return
    }
    $exitCode = Invoke-Native -FilePath "$env:SystemRoot\System32\sc.exe" -Arguments @('delete', $serviceName) -AllowedExitCodes @(0, 1060, 1072)
    if ($exitCode -eq 1072) {
        $script:RebootRequired = $true
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 250
        $service = Get-ServiceRecord
    } while ($service -and [DateTime]::UtcNow -lt $deadline)
    if ($service) {
        $script:RebootRequired = $true
        Write-Output "$serviceName remains marked for deletion and will be removed after reboot."
    }
}

function Enable-RebootDeletionApi {
    if (-not ('MacSoft.NativeMethods' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace MacSoft {
    public static class NativeMethods {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern bool MoveFileEx(string existingFileName, string newFileName, int flags);
    }
}
'@
    }
}

function Schedule-TreeForRebootDeletion {
    param([string]$Path)

    Enable-RebootDeletionApi
    $items = @(
        Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction SilentlyContinue |
            Sort-Object { $_.FullName.Length } -Descending
    )
    $items += Get-Item -LiteralPath $Path -Force
    foreach ($item in $items) {
        if (-not [MacSoft.NativeMethods]::MoveFileEx($item.FullName, $null, 4)) {
            $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw "Could not schedule reboot deletion for $($item.FullName). Win32=$errorCode"
        }
    }
    $script:RebootRequired = $true
}

function Remove-DataIfRequested {
    if ($PurgeData -ne 1 -or -not (Test-Path -LiteralPath $DataRoot)) {
        return
    }
    try {
        Remove-Item -LiteralPath $DataRoot -Recurse -Force -ErrorAction Stop
    } catch {
        Schedule-TreeForRebootDeletion -Path $DataRoot
    }
}

function Remove-FirewallRuleChecked {
    $rules = @(
        Get-NetFirewallRule -DisplayName $firewallRule -ErrorAction SilentlyContinue
    )
    foreach ($rule in $rules) {
        Remove-NetFirewallRule -InputObject $rule -ErrorAction Stop
    }
}

if ($Action -eq 'PreInstall') {
    $servicePresent = $null -ne (Get-ServiceRecord)
    $programRootPresent = Test-Path -LiteralPath $ProgramRoot -PathType Container
    Write-Output "Pre-install state: service=$servicePresent programRoot=$programRootPresent"
    Stop-OwnedServiceTree
    Stop-InstalledProgramProcesses
    Write-Output 'Pre-install cleanup completed.'
}

if ($Action -eq 'Cleanup') {
    Stop-OwnedServiceTree
    Stop-InstalledProgramProcesses
    Remove-ServiceChecked
    Remove-FirewallRuleChecked
    Remove-DataIfRequested
}

if ($script:RebootRequired) {
    Write-Output 'Cleanup is safely scheduled and requires a Windows restart.'
    exit 3010
}
Write-Output 'Cleanup completed.'
exit 0
