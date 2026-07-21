@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "HERMES_HOME=%PROJECT_ROOT%runtime"

if not exist "%HERMES_HOME%\config.yaml" (
    echo [ERROR] MacSoft Agent runtime is missing: %HERMES_HOME%
    exit /b 1
)

cd /d "%PROJECT_ROOT%hermes"
start "MacSoft Agent Desktop Renderer" /b cmd.exe /d /c "call npm.cmd run dev:renderer --workspace apps/desktop"
powershell.exe -NoProfile -Command "$deadline=(Get-Date).AddSeconds(60); do { if (Get-NetTCPConnection -State Listen -LocalPort 5174 -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [ERROR] MacSoft Agent Desktop renderer did not start on port 5174.
    exit /b 1
)

call npm.cmd run dev:electron --workspace apps/desktop

endlocal
