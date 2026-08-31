#!/bin/bash
# =====================================================================
# SourceSeal / Red-Team-Tauri -- Arranque unificado para Replit v6.1
# Backend + Frontend (dist/) en un solo proceso, puerto :8001
# =====================================================================
# set -e  # removido: no matar todo si algo falla
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT=8001

echo ""
echo "======================================================"
echo "  SourceSeal Engine v6.1 -- Replit (unified)"
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

# -- 2. Limpiar paquetes pip que pisan los de Nix (python3.11 Y 3.12) --
# replit.nix usa python312, pero versiones anteriores usaban 3.11.
# Limpiar ambas para cubrir todos los casos.
for PYVER in python3.11 python3.12 python3.13; do
  PYSITE="$HOME/.local/lib/${PYVER}/site-packages"
  if [ -d "$PYSITE" ]; then
    for pkg in pydantic pydantic_core fastapi; do
      if ls "$PYSITE" 2>/dev/null | grep -qi "^${pkg}"; then
        echo "[start] Limpiando ${pkg}* pip-instalado (${PYVER}) que pisa el de Nix..."
        find "$PYSITE" -maxdepth 1 -iname "${pkg}*" -exec rm -rf {} + 2>/dev/null || true
      fi
    done
  fi
done

# -- 3. Deps Node + build frontend --
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ] || [ ! -d "node_modules/vis-network" ]; then
  echo "[start] Instalando dependencias Node..."
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -5 || true
fi
echo "[start] Build frontend..."
npm run build 2>&1 || {
  echo "[start] ! Build frontend fallo, pero continuando con dist/ existente..."
  echo "[start]   Si dist/ no existe, el backend no tendra frontend que servir."
}

# -- 4. Levantar backend unificado --
echo "[start] Iniciando backend unificado en :$PORT..."
cd "$ROOT/redteam/scripts"
export PORT=$PORT
export HOST=0.0.0.0
export PYTHONUNBUFFERED=1
if [ -f "$ROOT/commander/commander.py" ]; then
  export COMMANDER_DIR="$ROOT/commander"
  echo "[start] Commander detectado en $COMMANDER_DIR"
fi
python3 dashboard_server.py &
BACKEND_PID=$!
echo "[start] Backend PID: $BACKEND_PID"

# -- 5. Esperar y VERIFICAR --
READY=0
for i in $(seq 1 30); do
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
  echo "[start] X El backend no respondio tras 30s."
  echo "[start]    Revisa los logs arriba para ver el error real de arranque."
  exit 1
fi

echo ""
echo "[start] Sistema unificado corriendo:"
echo "        -> Backend + Frontend: http://0.0.0.0:$PORT"
echo "        -> Scanner: REAL (cero mocks)"
echo "        -> ARTO AI: AUTO-START (motor autonomo de operaciones)"
echo "        -> Health: http://localhost:$PORT/api/health"
echo "        -> ARTO Status: http://localhost:$PORT/api/arto/status"
echo ""

# -- 6. GHOST HUNTER PHANTOM (Master + Nodo en :8002) --
echo "[start] Iniciando GHOST HUNTER PHANTOM..."
cd "$ROOT/ghost_hunter_phantom"
BACKEND_API="http://localhost:$PORT" MASTER_PORT=8002 NUM_NODES=1 bash start.sh all &
GHOST_PID=$!
echo "[start] GHOST PHANTOM PID: $GHOST_PID"
cd "$ROOT"

echo ""
echo "[start] Sistema unificado corriendo:"
echo "        -> Backend + Frontend: http://0.0.0.0:$PORT"
echo "        -> GHOST PHANTOM Master: http://0.0.0.0:8002/api/status"
echo "        -> Scanner: REAL (cero mocks)"
echo "        -> ARTO AI: AUTO-START (motor autonomo de operaciones)"
echo "        -> Health: http://localhost:$PORT/api/health"
echo "        -> ARTO Status: http://localhost:$PORT/api/arto/status"
echo "        -> GHOST Status: http://localhost:8002/api/status"
echo ""

cleanup() {
  echo "[start] Apagando..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$GHOST_PID" 2>/dev/null || true
  pkill -f "dashboard_server.py" 2>/dev/null || true
  pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
  pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

wait "$BACKEND_PID"
