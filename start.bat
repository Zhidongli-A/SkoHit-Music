@echo off
chcp 65001 >nul
echo [SkoHit Music] 正在检查环境...

REM 检查 Git 是否安装
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Git，请先安装 Git
    echo.
    echo 安装方式：
    echo 1. 访问 https://git-scm.com/download/win 下载安装包
    echo 2. 或使用 winget 安装：winget install Git.Git
    echo.
    echo 安装完成后重新运行此脚本
    pause
    exit /b 1
)

echo [SkoHit Music] Git 已安装，启动服务...
python app.py %*
