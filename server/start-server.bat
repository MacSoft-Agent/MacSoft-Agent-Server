@echo off
setlocal

cd /d %~dp0

set PYTHONPATH=%CD%

.venv\Scripts\python.exe -m macsoft.server

endlocal
