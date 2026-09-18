@echo off
title MediaDownloaderBot - Runner
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Running setup first...
    call setup.bat
)

echo.
echo ===================================================
echo     MediaDownloaderBot - Starting
echo ===================================================
echo.

.\venv\Scripts\python.exe bot.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Bot stopped with an error.
    pause
)
