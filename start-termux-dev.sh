#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal — Modo DEV con polling (sin inotify)
# Usar SOLO si necesitas hot-reload en Termux
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$REDTEAM_API_KEY" ]; then
  read -rp "🔑 API Key: " REDTEAM_API_KEY
  export REDTEAM_API_KEY
fi

# Backend en background
pkill -f "node server.js" 2>/dev/null
sleep 1
cd "$SCRIPT_DIR"
node server.js > /tmp/backend.log 2>&1 &
echo "Backend PID: $!"
sleep 3

# Frontend DEV con polling (no inotify)
cd "$SCRIPT_DIR/tauri-frontend"
echo "Iniciando dev server con polling..."
export CHOKIDAR_USEPOLLING=1
npx vite --port 5173 --host 0.0.0.0
