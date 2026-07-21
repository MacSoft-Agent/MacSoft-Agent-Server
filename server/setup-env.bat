@echo off
setlocal

cd /d "%~dp0"

echo [MACSOFT_SETUP] Starting Python environment setup...
echo [MACSOFT_SETUP] Project directory: %cd%

if not exist "requirements.txt" (
    echo [MACSOFT_SETUP][ERROR] requirements.txt not found.
    echo [MACSOFT_SETUP][ERROR] Please run this file inside the server project directory.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [MACSOFT_SETUP] Creating virtual environment...
    python -m venv .venv

    if errorlevel 1 (
        echo [MACSOFT_SETUP][ERROR] Failed to create virtual environment.
        echo [MACSOFT_SETUP][ERROR] Please check whether Python is installed and added to PATH.
        pause
        exit /b 1
    )
) else (
    echo [MACSOFT_SETUP] Virtual environment already exists.
)

echo [MACSOFT_SETUP] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

if errorlevel 1 (
    echo [MACSOFT_SETUP][ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo [MACSOFT_SETUP] Installing dependencies from requirements.txt...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo [MACSOFT_SETUP][ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [MACSOFT_SETUP] Setup completed successfully.
echo [MACSOFT_SETUP] Virtual environment: .venv
echo.
pause
exit /b 0
