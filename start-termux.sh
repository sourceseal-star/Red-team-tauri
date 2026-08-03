#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal Red-team Console — ÚNICO script de inicio Termux
# Backend: Python dashboard_server.py en :8001
# Incluye: Canary SVG/HTML + Scan cámaras/routers/radio/antenna/IoT + WebSocket
# Frontend: servido por el backend en el mismo puerto
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
REDTEAM_DIR="$SCRIPT_DIR/redteam"
FRONTEND_DIR="$SCRIPT_DIR/tauri-frontend"
PID_DIR="$SCRIPT_DIR/.pids"

mkdir -p "$LOG_DIR" "$PID_DIR" \
         "$REDTEAM_DIR/reports" "$REDTEAM_DIR/evidence" \
         "$REDTEAM_DIR/evidence/canary" "$REDTEAM_DIR/evidence/screenshots" \
         "$REDTEAM_DIR/data" "$REDTEAM_DIR/logs"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SourceSeal Red-team Console v2.1             ║"
echo "║  Termux — Backend unificado en :8001          ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── API Key ──────────────────────────────────────────
if [ -z "$REDTEAM_API_KEY" ]; then
  read -rp "🔑 API Key del backend: " REDTEAM_API_KEY
  export REDTEAM_API_KEY
fi
echo "  API Key configurada ✅"

# ── Matar procesos anteriores ────────────────────────
pkill -f "dashboard_server.py" 2>/dev/null
pkill -f "canary_monitor.py" 2>/dev/null
sleep 1

# ── Verificar/instalar dependencias Python ────────────
echo "📦 Verificando dependencias Python..."
pip install -q psutil 2>/dev/null || true
pip install -q websocket-server 2>/dev/null || true

# ── Build del frontend si no existe ───────────────────
cd "$FRONTEND_DIR"
if [ ! -d "dist" ] || [ "$(find src -newer dist/index.html 2>/dev/null | wc -l)" -gt 0 ]; then
  echo "🔨 Compilando frontend..."
  if [ ! -d "node_modules" ]; then
    npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -3
  fi
  npx vite build 2>&1 | tail -5
  echo "  Build completo ✅"
else
  echo "  Frontend ya compilado ✅"
fi

# ── Arrancar backend Python ───────────────────────────
echo "🔧 Arrancando backend Python en :8001 ..."
cd "$REDTEAM_DIR"
PORT=8001 PYTHONUNBUFFERED=1 python3 scripts/dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_DIR/backend.pid"
echo "  PID backend: $BACKEND_PID"

# Esperar que el backend responda
echo -n "  Esperando backend"
READY=0
for i in $(seq 1 15); do
  sleep 1
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 "http://127.0.0.1:8001/health" 2>/dev/null)
  if [ "$CODE" = "200" ]; then
    echo " ✅"
    READY=1
    break
  fi
  echo -n "."
done

if [ "$READY" != "1" ]; then
  echo ""
  echo "❌ Backend no respondió. Últimas 20 líneas del log:"
  tail -20 "$LOG_DIR/backend.log"
  exit 1
fi

# ── Arrancar Canary Monitor (opcional) ────────────────
if [ -f "$REDTEAM_DIR/monitor/canary_monitor.py" ]; then
  echo "🔧 Arrancando Canary Monitor..."
  cd "$REDTEAM_DIR/monitor"
  nohup python3 canary_monitor.py --watch "$REDTEAM_DIR/evidence/canary" > "$LOG_DIR/canary_monitor.log" 2>&1 &
  MONITOR_PID=$!
  echo $MONITOR_PID > "$PID_DIR/canary_monitor.pid"
  echo "  PID monitor: $MONITOR_PID"
fi

# ── Obtener IP local ──────────────────────────────────
LOCAL_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
if [ -z "$LOCAL_IP" ]; then
  LOCAL_IP=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127 | awk '{print $2}' | head -1)
fi

# ── Resumen ───────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ SISTEMA RED-TEAM OPERATIVO"
echo ""
echo "  Dashboard:    http://localhost:8001"
echo "  API:          http://localhost:8001"
echo "  WebSocket:    ws://localhost:8001"
if [ -n "$LOCAL_IP" ]; then
  echo ""
  echo "  LAN:          http://$LOCAL_IP:8001"
fi
echo ""
echo "  Endpoints disponibles:"
echo "    POST /api/scan/cameras   — 20 cámaras IP"
echo "    POST /api/scan/routers   — 5 routers + 2 repetidores"
echo "    POST /api/scan/antenna   — Canal cerrado 450-470 MHz"
echo "    POST /api/scan/radio     — FM/AM 88-108 MHz"
echo "    POST /api/scan/iot       — MQTT/CoAP/Modbus/BACnet"
echo "    GET  /api/network/*      — Scan de red real (X-Api-Key)"
echo "    POST /api/canary/alert   — Recibe alertas canary"
echo "    GET  /api/canary/alerts  — Ver alertas"
echo "    GET  /canary/svg         — Callback SVG canary"
echo "    GET  /canary/html        — Callback HTML canary"
echo "    WS   /ws                 — Tiempo real"
echo ""
echo "  Logs:    tail -f $LOG_DIR/backend.log"
echo "  Detener: bash scripts/termux/stop_all.sh"
echo "═══════════════════════════════════════════════"
echo ""

# Trap para limpiar al salir
trap "echo ''; echo '🛑 Deteniendo...'; kill $BACKEND_PID ${MONITOR_PID:-} 2>/dev/null; exit 0" INT TERM

# Mostrar logs en vivo
tail -f "$LOG_DIR/backend.log" &
TAIL_PID=$!
trap "kill $BACKEND_PID ${MONITOR_PID:-} $TAIL_PID 2>/dev/null; exit 0" INT TERM

wait $BACKEND_PID
