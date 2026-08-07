#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal Engine v2.1-unified — Termux
# Backend único: dashboard_server.py en :8001
# Frontend: Vite dev server en :5173 (proxy → :8001)
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOG_DIR"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SourceSeal Engine v2.1-unified — Termux       ║"
echo "║  Backend Python :8001 + Vite :5173             ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── Matar procesos anteriores ────────────────────────
pkill -f "dashboard_server.py" 2>/dev/null
pkill -f "vite" 2>/dev/null
sleep 1

# ── Verificar deps Python ────────────────────────────
pip install -q fastapi uvicorn httpx psutil 2>/dev/null || true

# ── Verificar deps Node.js ───────────────────────────
cd "$SCRIPT_DIR/tauri-frontend"
if [ ! -d "node_modules" ]; then
  echo "📦 Instalando dependencias Node.js..."
  npm install 2>&1 | tail -3
fi

# ── Arrancar backend Python (:8001) ─────────────────
echo "🔧 Arrancando backend unificado en :8001 ..."
cd "$SCRIPT_DIR/redteam/scripts"
python3 dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"

echo -n "  Esperando backend"
for i in $(seq 1 10); do
  sleep 1
  if curl -s http://127.0.0.1:8001/ > /dev/null 2>&1; then
    echo " ✅"
    break
  fi
  echo -n "."
done

# ── Arrancar Vite (:5173) ────────────────────────────
echo "🎨 Arrancando Vite en :5173 ..."
cd "$SCRIPT_DIR/tauri-frontend"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

echo ""
echo "✅ Sistema corriendo:"
echo "   → Frontend: http://localhost:5173"
echo "   → Backend:  http://localhost:8001"
echo ""

# ── Mantener vivos ──────────────────────────────────
cleanup() {
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup SIGTERM SIGINT

while true; do
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "[watch] Backend caído, reiniciando..."
    cd "$SCRIPT_DIR/redteam/scripts"
    python3 dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
  fi
  sleep 5
done
