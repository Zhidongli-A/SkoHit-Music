#!/bin/bash

echo "[SkoHit Music] 正在检查环境..."

# 检查 Git 是否安装
if command -v git &> /dev/null; then
    echo "[SkoHit Music] Git 已安装，启动服务..."
    python3 app.py "$@"
    exit 0
fi

echo "[SkoHit Music] 未检测到 Git，正在自动安装..."

# 检测包管理器并安装 Git
if command -v apt &> /dev/null; then
    echo "[SkoHit Music] 使用 apt 安装 Git..."
    apt update && apt install -y git
elif command -v yum &> /dev/null; then
    echo "[SkoHit Music] 使用 yum 安装 Git..."
    yum install -y git
elif command -v dnf &> /dev/null; then
    echo "[SkoHit Music] 使用 dnf 安装 Git..."
    dnf install -y git
elif command -v pacman &> /dev/null; then
    echo "[SkoHit Music] 使用 pacman 安装 Git..."
    pacman -S --noconfirm git
elif command -v zypper &> /dev/null; then
    echo "[SkoHit Music] 使用 zypper 安装 Git..."
    zypper install -y git
elif command -v apk &> /dev/null; then
    echo "[SkoHit Music] 使用 apk 安装 Git..."
    apk add git
elif command -v brew &> /dev/null; then
    echo "[SkoHit Music] 使用 brew 安装 Git..."
    brew install git
else
    echo "[错误] 无法找到可用的包管理器，请手动安装 Git"
    exit 1
fi

# 再次检查 Git 是否安装成功
if command -v git &> /dev/null; then
    echo "[SkoHit Music] Git 安装成功，启动服务..."
    python3 app.py "$@"
else
    echo "[错误] Git 安装失败，请手动安装"
    exit 1
fi
