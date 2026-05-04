#!/bin/bash
# 服务器端自动部署脚本
# 使用方法：在服务器项目目录中运行 ./deploy.sh

echo "=========================================="
echo "SkoHit Music 自动部署脚本"
echo "=========================================="

# 保存当前目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "项目目录: $PROJECT_DIR"

# 1. 备份数据库（重要！）
if [ -d "data" ]; then
    echo "[1/5] 备份数据库..."
    mkdir -p backup
    cp data/users.json backup/users.json.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    cp data/favorites.json backup/favorites.json.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    echo "      ✓ 数据库已备份到 backup/ 目录"
else
    echo "[1/5] 数据库目录不存在，将在首次运行时自动创建"
fi

# 2. 拉取最新代码（注意：.gitignore 中的文件不会被覆盖）
# data/*.json 在 .gitignore 中，Git 不会跟踪这些文件
echo "[2/5] 拉取最新代码..."
git fetch origin
git reset --hard origin/master
echo "      ✓ 代码已更新（数据库文件不受影响）"

# 3. 安装依赖
echo "[3/5] 安装/更新依赖..."
pip install -r requirements.txt --quiet
echo "      ✓ 依赖已更新"

# 4. 初始化数据库（注意：如果文件已存在不会覆盖，只创建空文件）
echo "[4/5] 检查数据库..."
python -c "
import json_db
import os

# 检查现有数据
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

# 初始化（不会覆盖已有数据）
json_db.init_db()
print('      ✓ 数据库检查完成（已有数据安全）')
"

# 5. 重启服务
echo "[5/5] 重启服务..."
if systemctl is-active --quiet skohit-music 2>/dev/null; then
    sudo systemctl restart skohit-music
    echo "      ✓ 服务已重启"
elif pgrep -f "python.*app.py" > /dev/null; then
    # 杀死旧进程
    pkill -f "python.*app.py"
    sleep 2
    # 启动新进程（后台运行）
    nohup python app.py > app.log 2>&1 &
    echo "      ✓ 服务已重启（后台模式）"
else
    echo "      ! 服务未运行，请手动启动: python app.py"
fi

echo "=========================================="
echo "部署完成！"
echo "访问地址: http://$(hostname -I | awk '{print $1}'):7000"
echo "=========================================="
echo ""
echo "数据库安全提示："
echo "  - 本次部署不会删除或覆盖已有用户数据"
echo "  - 数据备份保存在 backup/ 目录"
echo "  - 如需恢复数据: cp backup/users.json.xxx data/users.json"
echo "=========================================="
