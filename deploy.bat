@echo off
chcp 65001 >nul
echo ==========================================
echo SkoHit Music 自动部署脚本
echo ==========================================

set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

echo 项目目录: %PROJECT_DIR%

:: 1. 备份数据库（重要！）
if exist "data" (
    echo [1/5] 备份数据库...
    if not exist "backup" mkdir backup
    
    :: 获取时间戳
    for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set dt=%%a
    set TIMESTAMP=%dt:~0,8%_%dt:~8,6%
    
    copy data\users.json backup\users.json.%TIMESTAMP% >nul 2>&1
    copy data\favorites.json backup\favorites.json.%TIMESTAMP% >nul 2>&1
    echo       数据库已备份到 backup\ 目录
) else (
    echo [1/5] 数据库目录不存在，将在首次运行时自动创建
)

:: 2. 拉取最新代码（data\*.json 在 .gitignore 中，不会被覆盖）
echo [2/5] 拉取最新代码...
git fetch origin
git reset --hard origin/master
echo       代码已更新（数据库文件不受影响）

:: 3. 安装依赖
echo [3/5] 安装/更新依赖...
pip install -r requirements.txt --quiet
echo       依赖已更新

:: 4. 初始化数据库（如果文件已存在不会覆盖）
echo [4/5] 检查数据库...
python -c "
import json_db
import os

users_exists = os.path.exists('data/users.json')
favorites_exists = os.path.exists('data/favorites.json')

if users_exists:
    users = json_db.get_all_users()
    print(f'      发现现有用户数据: {len(users)} 个用户')
else:
    print('      用户数据库不存在，将创建空文件')

if favorites_exists:
    favorites = json_db._load_json('data/favorites.json')
    print(f'      发现现有收藏数据: {len(favorites)} 条记录')
else:
    print('      收藏数据库不存在，将创建空文件')

json_db.init_db()
print('      数据库检查完成（已有数据安全）')
"

:: 5. 重启服务
echo [5/5] 重启服务...
taskkill /F /IM "python.exe" >nul 2>&1
timeout /t 2 /nobreak >nul

:: 使用 start 命令后台运行
start /B python app.py > app.log 2>&1

echo ==========================================
echo 部署完成！
echo 访问地址: http://localhost:7000
echo ==========================================
echo.
echo 数据库安全提示：
echo   - 本次部署不会删除或覆盖已有用户数据
echo   - 数据备份保存在 backup\ 目录
echo   - 如需恢复数据: copy backup\users.json.xxx data\users.json
echo ==========================================

pause
