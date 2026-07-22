@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-test-runtime.ps1"
exit /b %ERRORLEVEL%
