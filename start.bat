@echo off
chcp 65001 >nul
echo [SkoHit Music] 正在检查环境...

REM 检查 Git 是否安装
git --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [SkoHit Music] Git 已安装，启动服务...
    goto :run
)

echo [SkoHit Music] 未检测到 Git，正在自动安装...

REM 尝试使用 winget 安装 Git
echo [SkoHit Music] 正在通过 winget 安装 Git...
winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements

if %errorlevel% equ 0 (
    echo [SkoHit Music] Git 安装成功，启动服务...
    goto :run
)

REM winget 失败，尝试使用 Chocolatey
echo [SkoHit Music] winget 安装失败，尝试 Chocolatey...
choco install git -y

if %errorlevel% equ 0 (
    echo [SkoHit Music] Git 安装成功，启动服务...
    goto :run
)

REM 如果都失败了，输出错误信息
echo [错误] 自动安装 Git 失败，请手动安装
exit /b 1

:run
python app.py %*
