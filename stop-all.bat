@echo off
setlocal

echo Close MacSoft Agent Desktop before continuing.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-runtime.ps1"

endlocal
