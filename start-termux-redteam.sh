#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal Red-team Console — Modo Termux UNIFICADO
# Backend: Python (dashboard_server.py) en :8001
# Frontend: Vite build estático en :5000
# Canary SVG/HTML + Scan cámaras/routers/radio
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
REDTEAM_DIR="$SCRIPT_DIR/redteam"
FRONTEND_DIR="$SCRIPT_DIR/tauri-frontend"

mkdir -p "$LOG_DIR" "$REDTEAM_DIR/reports" "$REDTEAM_DIR/evidence" \
         "$REDTEAM_DIR/data" "$REDTEAM_DIR/logs"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SourceSeal Red-team Console — Termux         ║"
echo "║  Backend: Python (canary + scan) en :8001     ║"
echo "║  Frontend: Vite preview en :5000              ║"
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
pkill -f "vite.*preview" 2>/dev/null
sleep 1

# ── Instalar dependencias Python ──────────────────────
echo "📦 Verificando dependencias Python..."
pip install -q psutil 2>/dev/null || true

# ── Build del frontend si no existe ───────────────────
cd "$FRONTEND_DIR"
if [ ! -d "dist" ] || [ "$(find src -newer dist/index.html 2>/dev/null | wc -l)" -gt 0 ]; then
  echo "🔨 Compilando frontend..."
  if [ ! -d "node_modules" ]; then
    npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -3
  fi
  npx vite build 2>&1 | tail -5
  echo "  Build completo ✅"
fi

# ── Arrancar backend Python ───────────────────────────
echo "🔧 Arrancando backend Python en :8001 ..."
cd "$REDTEAM_DIR"
PORT=8001 PYTHONUNBUFFERED=1 python3 scripts/dashboard_server.py > "$LOG_DIR/redteam-backend.log" 2>&1 &
BACKEND_PID=$!
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
  echo "❌ Backend no respondió. Log:"
  tail -20 "$LOG_DIR/redteam-backend.log"
  exit 1
fi

# ── El backend Python (:8001) ya sirve el dist/ del frontend ─────────
# No necesitamos Vite preview — el dashboard_server.py maneja ambas cosas:
# /api/* → backend Python, /* → archivos estáticos del dist/
echo "🌐 Frontend servido por backend Python en :8001"
echo "  (dashboard_server.py sirve dist/ para rutas no-/api)"
sleep 1

# Obtener IP local
LOCAL_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
if [ -z "$LOCAL_IP" ]; then
  LOCAL_IP=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127 | awk '{print $2}' | head -1)
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Sistema RED-TEAM operativo"
echo ""
echo "  Dashboard:    http://localhost:8001"
echo "  API:          http://localhost:8001"
echo "  Swagger:      http://localhost:8001/health"
echo "  Canary:       http://localhost:8001/canary/svg"
echo ""
if [ -n "$LOCAL_IP" ]; then
  echo "  LAN Dashboard: http://$LOCAL_IP:5000"
  echo "  LAN API:       http://$LOCAL_IP:8001"
  echo ""
  echo "  Desde Replit:  configurar proxy a $LOCAL_IP:8001"
fi
echo ""
echo "  Módulos activos:"
echo "    • SVG/HTML Canary (captura de pantalla)"
echo "    • Scan de cámaras IP (28 puertos)"
echo "    • Scan de routers/repetidores (23 puertos)"
echo "    • Scan de radio/streaming (20 puertos)"
echo "    • Geo + Threat Intel"
echo "    • Honeypot + Deception"
echo ""
echo "  Log backend:  tail -f $LOG_DIR/redteam-backend.log"
echo "  Log frontend: tail -f $LOG_DIR/redteam-frontend.log"
echo ""
echo "  Presiona Ctrl+C para detener"
echo "═══════════════════════════════════════════════"

# Trap para limpiar al salir
trap "echo ''; echo '🛑 Deteniendo...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM

# Mostrar logs del backend en vivo
tail -f "$LOG_DIR/redteam-backend.log" &
TAIL_PID=$!
trap "kill $BACKEND_PID $TAIL_PID 2>/dev/null; exit 0" INT TERM

wait $BACKEND_PID
