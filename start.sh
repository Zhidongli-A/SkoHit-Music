#!/bin/bash

echo "[StartSh] Checking environment..."

# Check if Git is installed
if ! command -v git &> /dev/null; then
    echo "[StartSh] [ERROR] Git is not installed!"
    echo "[StartSh] Please install Git first"
    exit 1
fi

echo "[StartSh] Git is installed, starting server..."
python3 app.py "$@"
