@echo off
chcp 65001 >nul 2>&1
echo [SkoHit Music] Checking environment...

REM Check if Git is installed
git --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [SkoHit Music] Git is installed, starting server...
    goto :run
)

echo [SkoHit Music] Git not found, installing automatically...

REM Try to install Git using winget
echo [SkoHit Music] Installing Git via winget...
winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements

if %errorlevel% equ 0 (
    echo [SkoHit Music] Git installed successfully, starting server...
    goto :run
)

REM If winget fails, try Chocolatey
echo [SkoHit Music] winget failed, trying Chocolatey...
choco install git -y

if %errorlevel% equ 0 (
    echo [SkoHit Music] Git installed successfully, starting server...
    goto :run
)

REM If all methods fail
echo [Error] Failed to install Git automatically, please install manually
echo Download from: https://git-scm.com/download/win
pause
exit /b 1

:run
python app.py %*
