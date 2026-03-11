@echo off
title YC Status Monitor - Installer
echo.
echo  ================================================
echo   YC Status Monitor - Quick Installer (Windows)
echo  ================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed!
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo  [1/3] Installing Python dependencies...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed.

echo.
echo  [2/3] Installing browser engine...
playwright install chromium
echo  [OK] Browser ready.

echo.
echo  [3/3] Launching setup wizard...
echo.
echo  ------------------------------------------------
echo   Your browser will open at http://localhost:5959
echo   Follow the 3-step setup:
echo     1. Log into your YC account
echo     2. Enter Telegram Bot Token
echo     3. Enter Telegram Chat ID
echo  ------------------------------------------------
echo.
python web_ui.py
pause
