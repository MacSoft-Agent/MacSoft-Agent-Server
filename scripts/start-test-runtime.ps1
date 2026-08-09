[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Python = Join-Path $ProjectRoot 'hermes\venv\Scripts\python.exe'
$NodeModules = Join-Path $ProjectRoot 'hermes\node_modules'
$StateDirectory = Join-Path $ProjectRoot 'server\data\host'
$StatePath = Join-Path $StateDirectory 'test-runtime.json'
$ControlPath = Join-Path $StateDirectory 'host-control.json'
$DesktopOutput = Join-Path $ProjectRoot 'logs\test-desktop.out.log'
$DesktopError = Join-Path $ProjectRoot 'logs\test-desktop.err.log'
$DesktopUserData = Join-Path $ProjectRoot 'runtime\desktop-test-user-data'
$RequiredPorts = @(8766, 8643, 8642, 8787, 5174)
$InstalledHostServiceName = 'MacSoftAgentHost'

function Normalize-ProcessPath {
    $pathValues = @(
        [Environment]::GetEnvironmentVariables().GetEnumerator() |
            Where-Object { $_.Key -ieq 'Path' } |
            ForEach-Object { [string]$_.Value }
    )

    if ($pathValues.Count -gt 1) {
        Remove-Item Env:Path -ErrorAction SilentlyContinue
        $env:Path = ($pathValues -join ';')
    }
}

function Get-ListeningPortRecords {
    try {
        return @(
            Get-NetTCPConnection -State Listen -ErrorAction Stop |
                Select-Object LocalPort, OwningProcess
        )
    } catch {
        return @(
            netstat -ano |
                Select-String 'LISTENING' |
                ForEach-Object {
                    if ($_.Line -match ':([0-9]+)\s+\S+\s+LISTENING\s+([0-9]+)\s*$') {
                        [pscustomobject]@{
                            LocalPort = [int]$matches[1]
                            OwningProcess = [int]$matches[2]
                        }
                    }
                }
        )
    }
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

function Get-ServiceExecutablePath {
    param([string]$PathName)

    $value = $PathName.Trim()
    if ($value.StartsWith('"')) {
        $closingQuote = $value.IndexOf('"', 1)
        if ($closingQuote -gt 1) {
            return $value.Substring(1, $closingQuote - 1)
        }
    }
    return ($value -split '\s+', 2)[0]
}

function Stop-ControlledInstalledHost {
    param([object[]]$OccupiedPorts)

    $service = Get-CimInstance Win32_Service -Filter "Name='$InstalledHostServiceName'" -ErrorAction SilentlyContinue
    if (-not $service -or [int]$service.ProcessId -le 0) {
        return $false
    }

    $executablePath = Get-ServiceExecutablePath -PathName ([string]$service.PathName)
    $normalizedExecutable = $executablePath.Replace('/', '\')
    if (
        [IO.Path]::GetFileName($normalizedExecutable) -ine 'pythonservice.exe' -or
        $normalizedExecutable -inotmatch '\\MacSoft Agent\\python\\pythonservice\.exe$'
    ) {
        return $false
    }

    $ownedProcessIds = New-Object 'System.Collections.Generic.HashSet[int]'
    [void]$ownedProcessIds.Add([int]$service.ProcessId)
    foreach ($childProcessId in @(Get-DescendantProcessIds -RootProcessId ([int]$service.ProcessId))) {
        [void]$ownedProcessIds.Add([int]$childProcessId)
    }
    foreach ($listener in $OccupiedPorts) {
        if (-not $ownedProcessIds.Contains([int]$listener.OwningProcess)) {
            return $false
        }
    }

    Write-Host "Installed MacSoft Agent Host owns the development ports; requesting a controlled service stop."
    $serviceController = Join-Path $env:SystemRoot 'System32\sc.exe'
    $isAdministrator = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if ($isAdministrator) {
        $output = & $serviceController stop $InstalledHostServiceName 2>&1
        if ($LASTEXITCODE -notin @(0, 1062)) {
            throw "Windows could not stop $InstalledHostServiceName (exit $LASTEXITCODE): $output"
        }
    } else {
        try {
            $stopProcess = Start-Process -FilePath $serviceController -ArgumentList @('stop', $InstalledHostServiceName) -Verb RunAs -Wait -PassThru -WindowStyle Hidden
        } catch {
            throw "Administrator approval is required to stop the installed MacSoft Agent Host for development mode. $($_.Exception.Message)"
        }
        if ($stopProcess.ExitCode -notin @(0, 1062)) {
            throw "Windows could not stop $InstalledHostServiceName (exit $($stopProcess.ExitCode))."
        }
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        $remaining = @(
            Get-ListeningPortRecords |
                Where-Object { $RequiredPorts -contains $_.LocalPort }
        )
        $currentService = Get-Service -Name $InstalledHostServiceName -ErrorAction SilentlyContinue
        if ($remaining.Count -eq 0 -and (-not $currentService -or $currentService.Status -eq 'Stopped')) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)

    $summary = ($remaining | ForEach-Object { "$($_.LocalPort):$($_.OwningProcess)" }) -join ', '
    throw "The installed MacSoft Agent Host did not release the development ports within 30 seconds: $summary"
}

function Assert-CurrentGitDesktopSource {
    $chatSourcePath = Join-Path $ProjectRoot 'hermes\apps\desktop\src\app\chat\index.tsx'
    $sidebarSourcePath = Join-Path $ProjectRoot 'hermes\apps\desktop\src\app\chat\sidebar\index.tsx'
    $chatContent = Get-Content -LiteralPath $chatSourcePath -Raw
    $sidebarContent = Get-Content -LiteralPath $sidebarSourcePath -Raw

    if (
        -not $chatContent.Contains('macSoftAdminChat') -or
        $chatContent.Contains('MacSoftAdminChatSurface') -or
        -not $sidebarContent.Contains("SIDEBAR_NAV.filter")
    ) {
        throw 'The current Git Desktop source markers are missing or an old Admin surface is still present.'
    }

    Write-Host 'Current-Git Desktop source verified on disk; Vite 5174 will serve this workspace.'
}

function Stop-StaleCurrentGitElectron {
    $currentGitElectronPath = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'hermes\node_modules\electron\dist\electron.exe'))
    $staleProcesses = @(
        Get-Process -Name 'electron' -ErrorAction SilentlyContinue |
            Where-Object {
                try {
                    [IO.Path]::GetFullPath($_.Path) -ieq $currentGitElectronPath
                } catch {
                    $false
                }
            }
    )

    foreach ($process in $staleProcesses) {
        Write-Host "Stopping stale current-Git Electron process $($process.Id)."
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

foreach ($marker in @(
    (Join-Path $ProjectRoot 'product.json'),
    (Join-Path $ProjectRoot 'server\macsoft'),
    (Join-Path $ProjectRoot 'hermes\apps\desktop'),
    (Join-Path $ProjectRoot 'product_runtime'),
    (Join-Path $ProjectRoot 'packaging')
)) {
    if (-not (Test-Path -LiteralPath $marker)) {
        throw "MacSoft Agent source marker is missing: $marker"
    }
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'hermes\venv is missing. Rebuild the uv environment before starting the test runtime.'
}
if (-not (Test-Path -LiteralPath $NodeModules -PathType Container)) {
    throw 'hermes\node_modules is missing. Run npm ci in hermes before starting the test runtime.'
}

Normalize-ProcessPath
Assert-CurrentGitDesktopSource
Stop-StaleCurrentGitElectron

$occupied = @(
    Get-ListeningPortRecords |
        Where-Object { $RequiredPorts -contains $_.LocalPort }
)
if ($occupied.Count -gt 0) {
    [void](Stop-ControlledInstalledHost -OccupiedPorts $occupied)
    $occupied = @(
        Get-ListeningPortRecords |
            Where-Object { $RequiredPorts -contains $_.LocalPort }
    )
    if ($occupied.Count -gt 0) {
        $summary = ($occupied | ForEach-Object { "$($_.LocalPort):$($_.OwningProcess)" }) -join ', '
        throw "MacSoft Agent test ports are occupied by an unknown or mixed process owner: $summary"
    }
}

New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DesktopOutput) | Out-Null
$hostArguments = @(
    '-m',
    'product_runtime.macsoft_runtime.cli',
    '--mode',
    'development',
    '--program-root',
    $ProjectRoot
)
$hostProcess = Start-Process -FilePath $Python -ArgumentList $hostArguments -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden
@{
    pid = $hostProcess.Id
    project_root = $ProjectRoot
    started_at = [DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8

try {
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    $ready = $false
    do {
        if ($hostProcess.HasExited) {
            throw "MacSoft Agent test Host exited with code $($hostProcess.ExitCode)."
        }
        if (Test-Path -LiteralPath $ControlPath -PathType Leaf) {
            try {
                $control = Get-Content -LiteralPath $ControlPath -Raw | ConvertFrom-Json
                $headers = @{ Authorization = "Bearer $($control.token)" }
                $status = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/v1/status' -Headers $headers -TimeoutSec 2
                if ($status.runtime_compatibility.status -eq 'rejected') {
                    $reason = [string]$status.runtime_compatibility.message
                    throw "Hermes runtime compatibility check failed: $reason"
                }
                $services = @($status.services.PSObject.Properties.Value)
                $ready = $status.ok -eq $true -and $services.Count -eq 3 -and @($services | Where-Object { $_.status -ne 'running' }).Count -eq 0
            } catch {
                if ($_.Exception.Message -like 'Hermes runtime compatibility check failed:*') {
                    throw
                }
                $ready = $false
            }
        }
        if (-not $ready) {
            Start-Sleep -Milliseconds 500
        }
    } while (-not $ready -and [DateTime]::UtcNow -lt $deadline)

    if (-not $ready) {
        throw 'MacSoft Agent test Host did not make all four services healthy within 90 seconds.'
    }

    Write-Host 'MacSoft Agent test runtime is ready: Host 8766, Config 8643, AI 8642, Server 8787.'
    Write-Host 'Starting current-Git Server Desktop test mode on Vite 5174.'
    Write-Host "Using isolated Desktop user data and single-instance lock: $DesktopUserData"
    $env:HERMES_HOME = Join-Path $ProjectRoot 'runtime'
    $env:MACSOFT_AGENT_ROOT = $ProjectRoot
    $env:GITHUB_SHA = '0000000000000000000000000000000000000000'
    $env:HERMES_DESKTOP_USER_DATA_DIR = $DesktopUserData
    $env:HERMES_DESKTOP_DEV_SERVER = 'http://127.0.0.1:5174'
    New-Item -ItemType Directory -Force -Path $DesktopUserData | Out-Null
    $desktopProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev:macsoft', '--workspace', 'apps/desktop') -WorkingDirectory (Join-Path $ProjectRoot 'hermes') -PassThru -WindowStyle Hidden -RedirectStandardOutput $DesktopOutput -RedirectStandardError $DesktopError
    $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    $state | Add-Member -NotePropertyName desktop_pid -NotePropertyValue $desktopProcess.Id -Force
    $state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8
    $desktopProcess.WaitForExit()
    if ($desktopProcess.ExitCode -ne 0 -and (Test-Path -LiteralPath $StatePath)) {
        throw "Desktop test mode exited with code $($desktopProcess.ExitCode). See logs\test-desktop.err.log."
    }
} finally {
    & (Join-Path $PSScriptRoot 'stop-test-runtime.ps1') -Quiet
}
