@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-test-runtime.ps1"
exit /b %ERRORLEVEL%
