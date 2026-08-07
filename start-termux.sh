#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal Engine v2.1 — Inicio para Termux
# Backend Node.js (server.js) en :3000 — Dashboard + IoT + Geo + Intel
# Backend Python (FastAPI) en :8000 — Scan avanzado + Canary + Exploits
# Frontend Vite en :5173 — Dashboard React
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/.pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SourceSeal Engine v2.1 — Termux               ║"
echo "║  Node.js :3000 + FastAPI :8000 + Vite :5173    ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── Matar procesos anteriores ────────────────────────
pkill -f "node server.js" 2>/dev/null
pkill -f "main.py" 2>/dev/null
pkill -f "vite" 2>/dev/null
sleep 1

# ── Pedir API key si no está seteada ──────────────────
if [ -z "$REDTEAM_API_KEY" ]; then
  read -rp "🔑 API Key del backend: " REDTEAM_API_KEY
  export REDTEAM_API_KEY
fi

# ── Verificar dependencias Node.js ────────────────────
cd "$SCRIPT_DIR"
if [ ! -d "node_modules/express" ]; then
  echo "📦 Instalando dependencias Node.js..."
  npm install 2>&1 | tail -3
fi

# ── Arrancar backend Node.js (:3000) ──────────────────
echo "🔧 Arrancando Node.js en :3000 ..."
node server.js > "$LOG_DIR/node-backend.log" 2>&1 &
NODE_PID=$!
echo $NODE_PID > "$PID_DIR/node-backend.pid"
echo "  PID: $NODE_PID"

echo -n "  Esperando Node.js"
READY=0
for i in $(seq 1 10); do
  sleep 1
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 \
    -H "Authorization: Bearer $REDTEAM_API_KEY" \
    "http://127.0.0.1:3000/api/status" 2>/dev/null)
  if [ "$CODE" = "200" ]; then
    echo " ✅"
    READY=1
    break
  fi
  echo -n "."
done

if [ "$READY" != "1" ]; then
  echo ""
  echo "❌ Node.js no respondió. Log:"
  tail -20 "$LOG_DIR/node-backend.log"
  exit 1
fi

# ── Arrancar backend FastAPI (:8000) opcional ────────
echo "🔧 Arrancando FastAPI en :8000 ..."
pip install -q fastapi uvicorn pydantic 2>/dev/null || true
cd "$SCRIPT_DIR/backend"
PORT=8000 PYTHONUNBUFFERED=1 python3 main.py > "$LOG_DIR/python-backend.log" 2>&1 &
PY_PID=$!
echo $PY_PID > "$PID_DIR/python-backend.pid"
echo "  PID: $PY_PID"

# No bloqueamos si Python falla — Node.js tiene la mayoría de endpoints
sleep 2
if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:8000/health" 2>/dev/null; then
  echo "  ✅ FastAPI listo"
else
  echo "  ⚠️  FastAPI no disponible (opcional, continuar sin él)"
fi

# ── Frontend — build o dev ────────────────────────────
cd "$SCRIPT_DIR/tauri-frontend"

if [ ! -d "node_modules" ]; then
  echo "📦 Instalando dependencias del frontend..."
  npm install 2>&1 | tail -3
fi

# Ver si hay que recompilar
if [ ! -d "dist" ] || [ "$(find src -newer dist/index.html 2>/dev/null | wc -l)" -gt 0 ]; then
  echo "🔨 Compilando frontend..."
  npx vite build 2>&1 | tail -5
fi

# ── Obtener IP local ──────────────────────────────────
LOCAL_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
[ -z "$LOCAL_IP" ] && LOCAL_IP=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127 | awk '{print $2}' | head -1)

# ── Resumen ───────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ SOURCESEAL ENGINE v2.1 OPERATIVO"
echo ""
echo "  Dashboard:    http://localhost:5173"
if [ -n "$LOCAL_IP" ]; then
  echo "  LAN:          http://$LOCAL_IP:5173"
fi
echo ""
echo "  Node.js API:  http://localhost:3000"
echo "  FastAPI:      http://localhost:8000/docs"
echo ""
echo "  Logs: tail -f $LOG_DIR/node-backend.log"
echo "  Stop: kill \$(cat $PID_DIR/*.pid)"
echo "═══════════════════════════════════════════════"
echo ""

# Trap para limpiar al salir
trap "echo ''; echo '🛑 Deteniendo...'; kill $NODE_PID $PY_PID 2>/dev/null; exit 0" INT TERM

# Servir frontend con vite preview (sin watchers, sin inotify)
npx vite preview --host 0.0.0.0 --port 5173
