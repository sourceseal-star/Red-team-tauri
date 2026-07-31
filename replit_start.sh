#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Restaurar auth de GitHub ──────────────────────────────────────────────────
bash "$ROOT/scripts/init_git_auth.sh" 2>/dev/null || true

# ── Crear directorios necesarios ──────────────────────────────────────────────
mkdir -p "$ROOT/redteam/reports" "$ROOT/redteam/evidence" \
         "$ROOT/redteam/data"   "$ROOT/redteam/logs"

# ── Instalar dependencias Python ──────────────────────────────────────────────
echo "[start] Instalando dependencias Python..."
pip install -q --no-cache-dir psutil 2>/dev/null || true
# Si hay requirements.txt en redteam, instalarlo
if [ -f "$ROOT/redteam/requirements.txt" ]; then
  pip install -q --no-cache-dir -r "$ROOT/redteam/requirements.txt" 2>&1 | tail -3 || true
fi

# ── Instalar dependencias Node del frontend ───────────────────────────────────
echo "[start] Instalando dependencias Node..."
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -5 || true
fi

# ── Levantar backend Python en puerto 8001 ────────────────────────────────────
echo "[start] Iniciando backend Python en :8001..."
cd "$ROOT/redteam"
export PORT=8001
export PYTHONUNBUFFERED=1
export SOURCESEAL_API="https://sourceseal.co"
python3 scripts/dashboard_server.py &
BACKEND_PID=$!
echo "[start] Backend PID: $BACKEND_PID"

# ── Esperar a que el backend esté listo (max 15s) ────────────────────────────
echo "[start] Esperando que el backend esté listo..."
for i in $(seq 1 15); do
  if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "[start] Backend listo en :8001 ✓"
    break
  fi
  sleep 1
done

# ── Levantar frontend React/Vite en puerto 5000 ───────────────────────────────
echo "[start] Iniciando frontend Vite en :5000 (proxy → :8001)..."
cd "$ROOT/tauri-frontend"
npm run dev &
FRONTEND_PID=$!
echo "[start] Frontend PID: $FRONTEND_PID"

# ── Mantener vivos ambos procesos ────────────────────────────────────────────
echo "[start] ✅ Sistema REAL corriendo:"
echo "        → Frontend: http://0.0.0.0:5000"
echo "        → Backend:  http://0.0.0.0:8001"
echo "        → Proxy /api/* → :8001 automático"

# Trap para matar ambos al salir
cleanup() {
  echo "[start] Apagando servicios..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Esperar a que alguno muera y reiniciar si es necesario
while true; do
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "[start] Backend caído, reiniciando..."
    cd "$ROOT/redteam"
    python3 scripts/dashboard_server.py &
    BACKEND_PID=$!
  fi
  if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "[start] Frontend caído, reiniciando..."
    cd "$ROOT/tauri-frontend"
    npm run dev &
    FRONTEND_PID=$!
  fi
  sleep 5
done
