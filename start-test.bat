@echo off
setlocal
echo MacSoft Agent current-Git development runtime
echo Source: %~dp0
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-test-runtime.ps1"
exit /b %ERRORLEVEL%
