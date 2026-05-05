#!/bin/bash

echo "[SkoHit Music] 正在检查环境..."

# 检查 Git 是否安装
if ! command -v git &> /dev/null; then
    echo "[错误] 未检测到 Git，请先安装 Git"
    echo ""
    echo "安装方式："
    
    # 检测操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt &> /dev/null; then
            echo "  sudo apt update && sudo apt install git"
        elif command -v yum &> /dev/null; then
            echo "  sudo yum install git"
        elif command -v pacman &> /dev/null; then
            echo "  sudo pacman -S git"
        else
            echo "  请使用系统的包管理器安装 git"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  brew install git"
        echo "或"
        echo "  访问 https://git-scm.com/download/mac 下载安装包"
    else
        echo "  请访问 https://git-scm.com/downloads 下载安装包"
    fi
    
    echo ""
    echo "安装完成后重新运行此脚本"
    exit 1
fi

echo "[SkoHit Music] Git 已安装，启动服务..."
python3 app.py "$@"
