#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SourceSeal Console — Termux (Android) — Backend Python completo
# FastAPI :8001 con dist/ estático, enhanced_recon, cameras, topology
# =====================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
START_GATEWAY="${START_GATEWAY:-1}"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; C='\033[0;36m'; N='\033[0m'

echo ""
echo -e "  ${C}╔══════════════════════════════════════════════╗${N}"
echo -e "  ${C}║  SourceSeal Console — Termux (Python)         ║${N}"
echo -e "  ${C}║  Backend FastAPI :${PORT}                        ║${N}"
echo -e "  ${C}╚══════════════════════════════════════════════╝${N}"
echo ""

# ─── 1. Wake Lock ──────────────────────────────────────────────────────
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock
  echo -e "${G}[wake-lock] Activo${N}"
else
  echo -e "${Y}[wake-lock] NO disponible. Instala: pkg install termux-api${N}"
fi
echo ""

# ─── 2. Verificar Python ────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${R}[ERROR] Python3 no instalado. Ejecuta: pkg install python${N}"
  exit 1
fi
echo -e "${G}[python] $(python3 --version)${N}"

# ─── 3. Verificar dependencias Python ──────────────────────────────────
echo -e "${Y}[deps] Verificando dependencias Python...${N}"
python3 -c "import fastapi, uvicorn, httpx, pydantic" 2>/dev/null || {
  echo -e "${Y}[deps] Instalando dependencias faltantes...${N}"
  pip install -q fastapi uvicorn httpx pydantic psutil aiohttp 2>&1 | tail -3
}
echo -e "${G}[deps] OK${N}"
echo ""

# ─── 4. Verificar/crear .env ────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  API_KEY=$(openssl rand -hex 24)
  cat > "$SCRIPT_DIR/.env" << EOF
REDTEAM_API_KEY=${API_KEY}
HOST=${HOST}
PORT=${PORT}
ALLOWED_ORIGINS=http://localhost:${PORT},http://127.0.0.1:${PORT}
EOF
  chmod 600 "$SCRIPT_DIR/.env"
  echo -e "${G}[env] .env creado. API Key: ${API_KEY:0:8}...${N}"
  echo -e "${Y}[env] GUARDA TU KEY: ${API_KEY}${N}"
else
  echo -e "${G}[env] .env existe${N}"
fi
export $(cat "$SCRIPT_DIR/.env" | grep -v '^#' | xargs)
echo ""

# ─── 5. Build frontend si no existe dist/ ──────────────────────────────
if [ ! -f "$SCRIPT_DIR/tauri-frontend/dist/index.html" ]; then
  echo -e "${Y}[build] Frontend no compilado. Compilando...${N}"
  cd "$SCRIPT_DIR/tauri-frontend"
  if [ ! -d "node_modules" ]; then
    npm install --legacy-peer-deps 2>&1 | tail -5
  fi
  npm run build 2>&1 | tail -10
  cd "$SCRIPT_DIR"
  echo -e "${G}[build] Frontend compilado${N}"
  echo ""
else
  echo -e "${G}[build] Frontend ya compilado (dist/)${N}"
  echo ""
fi

# ─── 6. Matar proceso anterior en el puerto ────────────────────────────
pkill -f "dashboard_server.py" 2>/dev/null || true
if [ "$START_GATEWAY" = "1" ]; then
  pkill -f "gateway/mesh_server.py" 2>/dev/null || true
fi
sleep 1

# ─── 7. Gateway Mesh (opcional, activo por defecto) ─────────────────────
GATEWAY_PID=""
if [ "$START_GATEWAY" = "1" ]; then
  echo -e "${Y}[gateway] Iniciando mesh en :${GATEWAY_PORT}...${N}"
  (
    cd "$SCRIPT_DIR/gateway"
    PORT="$GATEWAY_PORT" python3 mesh_server.py
  ) > "$SCRIPT_DIR/sourceseal-gateway.log" 2>&1 &
  GATEWAY_PID=$!

  GATEWAY_READY=0
  for i in $(seq 1 10); do
    if curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/health" >/dev/null 2>&1; then
      GATEWAY_READY=1
      break
    fi
    if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if [ "$GATEWAY_READY" = "1" ]; then
    echo -e "${G}[gateway] OK en :${GATEWAY_PORT}${N}"
  else
    echo -e "${Y}[gateway] No disponible; el dashboard principal continuará en :${PORT}${N}"
    GATEWAY_PID=""
  fi
fi

# ─── 8. ARRANCAR ────────────────────────────────────────────────────────
echo -e "${G}╔══════════════════════════════════════════════════╗${N}"
echo -e "${G}║  SourceSeal Console arrancando...                ║${N}"
echo -e "${G}║  Backend FastAPI :${PORT}                         ║${N}"
if [ "$START_GATEWAY" = "1" ]; then
  echo -e "${G}║  Gateway Mesh    :${GATEWAY_PORT}                         ║${N}"
fi
echo -e "${G}║  Navegador: http://localhost:${PORT}              ║${N}"
echo -e "${G}║  WiFi:     http://$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || echo 'TU_IP'):${PORT}  ║${N}"
echo -e "${G}║                                                  ║${N}"
echo -e "${G}║  Ctrl+C para detener                              ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
echo ""

# Backend Python completo — sirve API + dist/ en un solo puerto
cd "$SCRIPT_DIR/redteam/scripts"
cleanup() {
  if [ -n "$GATEWAY_PID" ]; then
    kill "$GATEWAY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
python3 dashboard_server.py
