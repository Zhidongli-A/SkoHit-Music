@echo off
chcp 65001 >nul 2>&1
echo [StartBat] Checking environment...

REM Check if Git is installed
git --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [StartBat] Git is installed, starting server...
    goto :run
)

echo [StartBat] Git not found, installing automatically...

REM Try to install Git using winget
echo [StartBat] Installing Git via winget...
winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements

if %errorlevel% equ 0 (
    echo [StartBat] Git installed successfully, starting server...
    goto :run
)

REM If winget fails, try Chocolatey
echo [StartBat] winget failed, trying Chocolatey...
choco install git -y

if %errorlevel% equ 0 (
    echo [StartBat] Git installed successfully, starting server...
    goto :run
)

REM If all methods fail
echo [StartBat] [ERROR] Failed to install Git automatically
echo [StartBat] Please download from: https://git-scm.com/download/win
pause
exit /b 1

:run
echo [StartBat] Starting SkoHit Music Server...
python app.py %*
