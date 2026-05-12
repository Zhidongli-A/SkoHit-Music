#!/bin/bash

echo "[SkoHit Music] Starting server..."
echo "[SkoHit Music] Version: ${APP_VERSION:-unknown}"
echo "[SkoHit Music] Meting API: ${METING_API_URL:-not set}"

# 启动应用
exec python3 app.py "$@"
