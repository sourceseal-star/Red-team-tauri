#!/bin/bash
set -e

cd "$(dirname "$0")/redteam"
mkdir -p reports evidence

export PORT=5000
export PYTHONUNBUFFERED=1

echo "[replit] Installing core dependencies..."
pip install -q --no-cache-dir -r requirements.txt 2>&1 | tail -5 || {
  echo "[replit] WARN: Some deps failed, continuing with stdlib..."
}

if [ ! -f scripts/dashboard_server.py ]; then
  echo "[replit] ERROR: scripts/dashboard_server.py not found"
  exit 1
fi

echo "[replit] Starting dashboard on port $PORT..."
exec python3 scripts/dashboard_server.py
