#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Restaurar auth de GitHub ──────────────────────────────────────────────────
bash "$ROOT/scripts/init_git_auth.sh" 2>/dev/null || true

# ── Crear directorios necesarios ──────────────────────────────────────────────
mkdir -p "$ROOT/redteam/reports" "$ROOT/redteam/evidence" \
         "$ROOT/redteam/data"   "$ROOT/redteam/logs"

# ── Instalar dependencias Python (solo psutil para recursos reales) ──────────
echo "[start] Instalando psutil..."
pip install -q --no-cache-dir psutil 2>/dev/null || true

# ── Instalar dependencias Node del frontend ───────────────────────────────────
echo "[start] Instalando dependencias Node..."
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -5 || true
fi

# ── Levantar backend Python en puerto 8001 ────────────────────────────────────
echo "[start] Iniciando backend REAL en :8001..."
cd "$ROOT/redteam"
export PORT=8001
export PYTHONUNBUFFERED=1
# SOURCESEAL_API se configura desde la UI (Settings) — no hardcodear aqui
python3 scripts/dashboard_server.py &
BACKEND_PID=$!
echo "[start] Backend PID: $BACKEND_PID"

# ── Esperar a que el backend esté listo (max 15s) ────────────────────────────
echo "[start] Esperando backend..."
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
echo "        → Scanner:  HTTP real (cero mocks)"
echo "        → Datos:    Reales (cero dummy)"

cleanup() {
  echo "[start] Apagando..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

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
