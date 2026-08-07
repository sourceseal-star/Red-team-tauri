#!/bin/bash
# =====================================================================
# SourceSeal / Red-Team-Tauri -- Arranque unificado para Replit
# Backend + Frontend (dist/) en un solo proceso, puerto :8001
# =====================================================================
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT=8001

echo ""
echo "======================================================"
echo "  SourceSeal Engine -- Replit (v3.0-unified)"
echo "======================================================"

# -- 1. Matar CUALQUIER proceso zombie en el puerto --
echo "[start] Liberando puerto :$PORT si esta ocupado..."
pkill -f "dashboard_server.py" 2>/dev/null || true
if command -v fuser >/dev/null 2>&1; then
  fuser -k ${PORT}/tcp 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  lsof -ti:${PORT} | xargs -r kill -9 2>/dev/null || true
fi
sleep 2

# -- 2. Deps Python (tambien en replit.nix, pero backup) --
pip install -q --no-cache-dir fastapi uvicorn httpx psutil 2>/dev/null || true

# -- 3. Deps Node + build frontend --
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
  echo "[start] Instalando dependencias Node..."
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -5 || true
fi
echo "[start] Build frontend..."
npm run build 2>&1 | tail -5

# -- 4. Levantar backend unificado --
echo "[start] Iniciando backend unificado en :$PORT..."
cd "$ROOT/redteam/scripts"
export PORT=$PORT
export HOST=0.0.0.0
export PYTHONUNBUFFERED=1
python3 dashboard_server.py &
BACKEND_PID=$!
echo "[start] Backend PID: $BACKEND_PID"

# -- 5. Esperar y VERIFICAR (verificacion simplificada) --
# FIX: Antes el script comparaba version con un grep que capturaba mal
# ("3.0" en vez de "3.0-unified") y luego MATABA el backend recien arrancado.
# Ahora solo verificamos HTTP 200 + que la respuesta contenga "unified".
READY=0
for i in $(seq 1 20); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[start] X El proceso backend (PID $BACKEND_PID) murio."
    echo "[start]    Revisa los logs arriba para ver el error real."
    exit 1
  fi
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/api/health" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    BODY=$(curl -s "http://localhost:$PORT/api/health" 2>/dev/null || echo "")
    if echo "$BODY" | grep -q "red-team-tauri-unified"; then
      echo "[start] OK Backend listo en :$PORT (health=200, unified)"
      READY=1
      break
    else
      echo "[start] Responde algo que no es nuestro backend. Matando zombie..."
      pkill -f "dashboard_server.py" 2>/dev/null || true
      sleep 2
    fi
  fi
  sleep 1
done

if [ "$READY" != "1" ]; then
  echo "[start] X El backend no respondio tras 20s."
  echo "[start]    Revisa los logs arriba para ver el error real de arranque."
  exit 1
fi

echo "[start] Sistema unificado corriendo:"
echo "        -> Backend + Frontend: http://0.0.0.0:$PORT"
echo "        -> Scanner: REAL (cero mocks)"
echo "        -> Health: http://localhost:$PORT/api/health"

cleanup() {
  echo "[start] Apagando..."
  kill "$BACKEND_PID" 2>/dev/null || true
  pkill -f "dashboard_server.py" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

wait "$BACKEND_PID"
