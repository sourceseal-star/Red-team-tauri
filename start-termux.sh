#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SourceSeal Engine — Termux
# Backend único :8001 (FastAPI, sirve /api + /ws)
# Frontend Vite dev server :5173 (proxy /api,/ws,/canary → :8001)
# =====================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PORT=8001
EXPECTED_VERSION="3.0-unified"
mkdir -p "$LOG_DIR"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SourceSeal Engine — Termux                    ║"
echo "║  Backend Python :$PORT + Vite :5173            ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── 1. Matar procesos anteriores (por nombre Y por puerto) ────────────
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
if command -v fuser >/dev/null 2>&1; then
  fuser -k ${PORT}/tcp 2>/dev/null || true
fi
sleep 1

# ── 2. Deps Python ──────────────────────────────────────────────────────
pip install -q fastapi uvicorn httpx psutil 2>/dev/null || true

# ── 3. Deps Node ────────────────────────────────────────────────────────
cd "$SCRIPT_DIR/tauri-frontend"
if [ ! -d "node_modules" ]; then
  echo "📦 Instalando dependencias Node.js..."
  npm install 2>&1 | tail -5
fi

# ── 4. Arrancar backend Python ──────────────────────────────────────────
echo "🔧 Arrancando backend unificado en :$PORT ..."
cd "$SCRIPT_DIR/redteam/scripts"
python3 dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"

echo -n "  Esperando backend"
READY=0
for i in $(seq 1 15); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo ""
    echo "❌ El backend murió al arrancar. Log:"
    tail -20 "$LOG_DIR/backend.log"
    exit 1
  fi
  VERSION=$(curl -s "http://127.0.0.1:$PORT/api/health" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || true)
  if [ "$VERSION" = "$EXPECTED_VERSION" ]; then
    echo " ✅ (version=$VERSION)"
    READY=1
    break
  fi
  sleep 1
  echo -n "."
done
if [ "$READY" != "1" ]; then
  echo ""
  echo "❌ El backend no respondió con la versión esperada. Log:"
  tail -20 "$LOG_DIR/backend.log"
  exit 1
fi

# ── 5. Arrancar Vite ─────────────────────────────────────────────────────
echo "🎨 Arrancando Vite en :5173 ..."
cd "$SCRIPT_DIR/tauri-frontend"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

echo ""
echo "✅ Sistema corriendo:"
echo "   → Frontend: http://localhost:5173"
echo "   → Backend:  http://localhost:$PORT  (version=$VERSION)"
echo ""
echo "   Logs: tail -f $LOG_DIR/backend.log"
echo "         tail -f $LOG_DIR/frontend.log"
echo ""

# ── 6. Watchdog: reinicia el backend si muere ────────────────────────────
cleanup() {
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup SIGTERM SIGINT

while true; do
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "[watch] Backend caído, reiniciando..."
    cd "$SCRIPT_DIR/redteam/scripts"
    python3 dashboard_server.py >> "$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
  fi
  if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "[watch] Frontend caído, reiniciando..."
    cd "$SCRIPT_DIR/tauri-frontend"
    npm run dev >> "$LOG_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
  fi
  sleep 5
done
