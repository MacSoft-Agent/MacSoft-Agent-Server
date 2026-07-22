@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "HERMES_HOME=%PROJECT_ROOT%runtime"

if not exist "%HERMES_HOME%\config.yaml" (
    echo [ERROR] MacSoft Agent runtime is missing: %HERMES_HOME%
    exit /b 1
)

cd /d "%PROJECT_ROOT%hermes"
set "MACSOFT_AGENT_ROOT=%PROJECT_ROOT%"
call npm.cmd run dev:macsoft --workspace apps/desktop

endlocal
