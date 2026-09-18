@echo off
title MediaDownloaderBot - Setup
cd /d "%~dp0"

echo ===================================================
echo     MediaDownloaderBot - Automated Setup
echo ===================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Python is not found in PATH!
    echo [!] Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

echo [*] Upgrading pip...
.\venv\Scripts\python.exe -m pip install --upgrade pip

echo [*] Installing required dependencies...
.\venv\Scripts\pip.exe install -r requirements.txt

echo.
echo ===================================================
echo   Setup completed successfully!
echo   You can now launch the bot using start.bat
echo ===================================================
echo.
pause
