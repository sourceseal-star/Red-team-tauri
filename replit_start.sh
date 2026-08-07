#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Instalar deps Python ──────────────────────────────────────────────────────
pip install -q --no-cache-dir fastapi uvicorn httpx psutil 2>/dev/null || true

# ── Instalar deps Node frontend ───────────────────────────────────────────────
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -5 || true
fi

# ── Build frontend → dist/ ────────────────────────────────────────────────────
echo "[start] Building frontend..."
npm run build 2>&1 | tail -3 || true

# ── Levantar backend unificado en :8001 ───────────────────────────────────────
echo "[start] Iniciando backend unificado en :8001..."
cd "$ROOT/redteam/scripts"
export PORT=8001
export PYTHONUNBUFFERED=1
python3 dashboard_server.py &
BACKEND_PID=$!
echo "[start] Backend PID: $BACKEND_PID"

# ── Esperar a que el backend esté listo ──────────────────────────────────────
for i in $(seq 1 15); do
  if curl -s http://localhost:8001/ > /dev/null 2>&1; then
    echo "[start] Backend listo en :8001 ✓"
    break
  fi
  sleep 1
done

# ── En Replit no hace falta Vite dev server — el backend sirve dist/ ──────────
echo "[start] ✅ Sistema unificado corriendo:"
echo "        → Backend + Frontend: http://0.0.0.0:8001"
echo "        → Scanner: REAL (cero mocks)"

cleanup() {
  echo "[start] Apagando..."
  kill $BACKEND_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

wait $BACKEND_PID
