#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal Engine v2.1 — ÚNICO script de inicio Termux
# Backend: FastAPI (main.py) en :8000 con Swagger en /docs
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/.pids"

mkdir -p "$LOG_DIR" "$PID_DIR" \
         "$SCRIPT_DIR/redteam/evidence/canary" "$SCRIPT_DIR/redteam/evidence/screenshots" \
         "$SCRIPT_DIR/redteam/data" "$SCRIPT_DIR/redteam/logs"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SourceSeal Engine v2.1                        ║"
echo "║  FastAPI Backend — Swagger en /docs            ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── Matar procesos anteriores ────────────────────────
pkill -f "main.py" 2>/dev/null
pkill -f "dashboard_server.py" 2>/dev/null
pkill -f "canary_monitor.py" 2>/dev/null
sleep 1

# ── Verificar/instalar dependencias Python ────────────
echo "📦 Verificando dependencias Python..."
pip install -q fastapi uvicorn pydantic python-nmap requests 2>/dev/null || true
pip install -q psutil websockets 2>/dev/null || true

# ── Arrancar backend FastAPI ─────────────────────────
echo "🔧 Arrancando FastAPI en :8000 ..."
cd "$SCRIPT_DIR/backend"
PORT=8000 PYTHONUNBUFFERED=1 python3 main.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_DIR/backend.pid"
echo "  PID backend: $BACKEND_PID"

# Esperar que el backend responda
echo -n "  Esperando backend"
READY=0
for i in $(seq 1 15); do
  sleep 1
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 "http://127.0.0.1:8000/health" 2>/dev/null)
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
if [ -f "$SCRIPT_DIR/redteam/monitor/canary_monitor.py" ]; then
  echo "🔧 Arrancando Canary Monitor..."
  cd "$SCRIPT_DIR/redteam/monitor"
  nohup python3 canary_monitor.py --watch "$SCRIPT_DIR/redteam/evidence/canary" > "$LOG_DIR/canary_monitor.log" 2>&1 &
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
echo "  ✅ SOURCESEAL ENGINE v2.1 OPERATIVO"
echo ""
echo "  Swagger:       http://localhost:8000/docs"
echo "  API:           http://localhost:8000"
echo "  WebSocket:     ws://localhost:8000/ws"
if [ -n "$LOCAL_IP" ]; then
  echo ""
  echo "  LAN Swagger:   http://$LOCAL_IP:8000/docs"
fi
echo ""
echo "  Endpoints disponibles:"
echo "    POST /api/scan/port       — Escaneo de puertos"
echo "    POST /api/scan/cameras    — Camaras IP (red real)"
echo "    POST /api/scan/routers    — 5 routers + 2 repetidores"
echo "    POST /api/scan/antenna    — Canal cerrado 450-470 MHz"
echo "    POST /api/scan/radio      — FM/AM 88-108 MHz"
echo "    POST /api/scan/iot        — MQTT/CoAP/Modbus/BACnet"
echo "    POST /api/scan/wifi       — WiFi scan"
echo "    POST /api/scan/topology   — Topologia de red"
echo "    GET  /api/network/cameras — Scan camaras (real)"
echo "    GET  /api/network/routers — Scan routers (real)"
echo "    GET  /api/network/radio   — Scan radio (real)"
echo "    POST /api/canary/generate — Generar token canary"
echo "    POST /api/canary/alert    — Recibe alertas canary"
echo "    GET  /api/canary/alerts   — Ver alertas canary"
echo "    GET  /api/canary/tokens   — Listar tokens canary"
echo "    GET  /canary/callback     — Callback SVG/HTML canary"
echo "    GET  /health              — Health check"
echo "    WS   /ws                  — Tiempo real"
echo "    GET  /api/exploits/list   — Exploits disponibles"
echo "    GET  /api/osint/shodan    — Shodan lookup"
echo "    GET  /api/osint/whois     — WHOIS"
echo "    POST /api/report/generate — Generar reporte"
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
