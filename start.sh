#!/bin/bash

echo "[StartSh] Checking environment..."

# Check if Git is installed
if command -v git &> /dev/null; then
    echo "[StartSh] Git is installed, starting server..."
    python3 app.py "$@"
    exit 0
fi

echo "[StartSh] Git not found, installing automatically..."

# Check if sudo is available
SUDO=""
if command -v sudo &> /dev/null; then
    SUDO="sudo"
fi

# Detect package manager and install Git
if command -v apt &> /dev/null; then
    echo "[StartSh] Installing Git via apt..."
    $SUDO apt update && $SUDO apt install -y git
elif command -v yum &> /dev/null; then
    echo "[StartSh] Installing Git via yum..."
    $SUDO yum install -y git
elif command -v dnf &> /dev/null; then
    echo "[StartSh] Installing Git via dnf..."
    $SUDO dnf install -y git
elif command -v pacman &> /dev/null; then
    echo "[StartSh] Installing Git via pacman..."
    $SUDO pacman -S --noconfirm git
elif command -v zypper &> /dev/null; then
    echo "[StartSh] Installing Git via zypper..."
    $SUDO zypper install -y git
elif command -v apk &> /dev/null; then
    echo "[StartSh] Installing Git via apk..."
    $SUDO apk add git
elif command -v brew &> /dev/null; then
    echo "[StartSh] Installing Git via brew..."
    brew install git
else
    echo "[StartSh] [ERROR] No package manager found, please install Git manually"
    exit 1
fi

# Verify Git installation
if command -v git &> /dev/null; then
    echo "[StartSh] Git installed successfully, starting server..."
    python3 app.py "$@"
else
    echo "[StartSh] [ERROR] Failed to install Git"
    exit 1
fi
