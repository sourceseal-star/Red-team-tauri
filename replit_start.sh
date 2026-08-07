#!/bin/bash
# =====================================================================
# SourceSeal / Red-Team-Tauri — Arranque unificado para Replit
# Backend + Frontend (dist/) en un solo proceso, puerto :8001
# =====================================================================
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT=8001
EXPECTED_VERSION="3.0-unified"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  SourceSeal Engine — Replit"
echo "════════════════════════════════════════════════════════"

# ── 1. Matar CUALQUIER proceso zombie en el puerto ────────────────────
# Este es el fix del "Address already in use": si un proceso anterior
# quedó vivo (crash a medias, restart del contenedor, etc.), el nuevo
# uvicorn nunca logra bindear el puerto y el script sigue de largo
# curl-eando al proceso VIEJO pensando que es el nuevo.
echo "[start] Liberando puerto :$PORT si está ocupado..."
pkill -f "dashboard_server.py" 2>/dev/null || true
if command -v fuser >/dev/null 2>&1; then
  fuser -k ${PORT}/tcp 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  lsof -ti:${PORT} | xargs -r kill -9 2>/dev/null || true
fi
sleep 1

# ── 2. Deps Python ─────────────────────────────────────────────────────
pip install -q --no-cache-dir fastapi uvicorn httpx psutil 2>/dev/null || true

# ── 3. Deps Node + build frontend ─────────────────────────────────────
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
  echo "[start] Instalando dependencias Node..."
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -5 || true
fi
echo "[start] Build frontend..."
npm run build 2>&1 | tail -5

# ── 4. Levantar backend unificado ─────────────────────────────────────
echo "[start] Iniciando backend unificado en :$PORT..."
cd "$ROOT/redteam/scripts"
export PORT=$PORT
export PYTHONUNBUFFERED=1
python3 dashboard_server.py &
BACKEND_PID=$!
echo "[start] Backend PID: $BACKEND_PID"

# ── 5. Esperar y VERIFICAR que es el proceso correcto (no uno viejo) ──
READY=0
for i in $(seq 1 20); do
  # Si el proceso que lanzamos ya murió (p.ej. port bind fail), abortar rápido
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[start] ❌ El proceso backend (PID $BACKEND_PID) murió antes de responder."
    echo "[start]    Esto normalmente significa que el puerto seguía ocupado."
    echo "[start]    Reintenta este script — ya debería estar libre."
    exit 1
  fi
  VERSION=$(curl -s "http://localhost:$PORT/api/health" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || true)
  if [ -n "$VERSION" ]; then
    if [ "$VERSION" = "$EXPECTED_VERSION" ]; then
      echo "[start] Backend listo en :$PORT ✓  (version=$VERSION)"
      READY=1
      break
    else
      echo "[start] ⚠️  Responde un backend con version=$VERSION (esperado $EXPECTED_VERSION)."
      echo "[start]    Probablemente un proceso viejo sigue vivo en :$PORT. Matándolo y reintentando..."
      pkill -f "dashboard_server.py" 2>/dev/null || true
      sleep 2
    fi
  fi
  sleep 1
done

if [ "$READY" != "1" ]; then
  echo "[start] ❌ El backend no respondió con la versión esperada tras 20s."
  echo "[start]    Revisa los logs arriba para ver el error real de arranque."
  exit 1
fi

echo "[start] ✅ Sistema unificado corriendo:"
echo "        → Backend + Frontend: http://0.0.0.0:$PORT"
echo "        → Scanner: REAL (cero mocks)"
echo "        → Version: $VERSION"

cleanup() {
  echo "[start] Apagando..."
  kill "$BACKEND_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

wait "$BACKEND_PID"
