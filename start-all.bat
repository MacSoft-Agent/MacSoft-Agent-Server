@echo off
setlocal

set "PROJECT_ROOT=%~dp0"

start "MacSoft Agent AI Service" cmd /k call "%PROJECT_ROOT%start-hermes-gateway.bat"
powershell.exe -NoProfile -Command "$deadline=(Get-Date).AddSeconds(60); do { try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8642/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [ERROR] MacSoft Agent AI Service did not become healthy on port 8642.
    exit /b 1
)

start "MacSoft Server" cmd /k call "%PROJECT_ROOT%start-macsoft-server.bat"
powershell.exe -NoProfile -Command "$deadline=(Get-Date).AddSeconds(60); do { try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8787/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [ERROR] MacSoft Server did not become healthy on port 8787.
    exit /b 1
)

call "%PROJECT_ROOT%start-hermes-desktop.bat"

endlocal
