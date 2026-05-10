@echo off
chcp 65001 >nul 2>&1
echo [StartBat] Checking environment...

REM Check if Git is installed
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [StartBat] [ERROR] Git is not installed!
    echo [StartBat] Please download from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [StartBat] Git is installed, starting server...
echo [StartBat] Starting SkoHit Music Server...
python app.py %*
