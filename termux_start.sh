#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
# SOURCESEAL — LEVANTAMIENTO COMPLETO EN TERMUX
# Inicia: Dashboard (8001), Commander (8003), Gateway (8080)
# Uso: bash termux_start.sh
# ════════════════════════════════════════════════════════════════════
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Colores
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; W='\033[1;37m'; N='\033[0m'
ok()   { echo -e "  ${G}✅${N} $1"; }
fail() { echo -e "  ${R}❌${N} $1"; }
warn() { echo -e "  ${Y}⚠️${N} $1"; }
info() { echo -e "  ${C}ℹ️${N} $1"; }

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────
PORT="${PORT:-8001}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
COMMANDER_PORT="${COMMANDER_PORT:-8003}"
START_GATEWAY="${START_GATEWAY:-1}"
START_COMMANDER="${START_COMMANDER:-0}"  # 0 = Commander in-process en 8001

# ─── 0. WAKE LOCK ────────────────────────────────────────────────────
echo ""
echo -e "${C}╔══════════════════════════════════════════════╗${N}"
echo -e "${C}║  SOURCESEAL — Levantamiento Completo          ║${N}"
echo -e "${C}║  Dashboard:${PORT}  Gateway:${GATEWAY_PORT}  Cmd:${COMMANDER_PORT}        ║${N}"
echo -e "${C}╚══════════════════════════════════════════════╝${N}"
echo ""

if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    ok "Wake-lock activo (pantalla no se apaga)"
else
    warn "termux-wake-lock no disponible — instala: pkg install termux-api"
fi

# ─── 1. VERIFICAR PYTHON ────────────────────────────────────────────
echo -e "\n${W}── 1/6 Verificando Python...${N}"
if ! command -v python3 >/dev/null 2>&1; then
    fail "Python3 no instalado. Ejecuta: pkg install python"
    exit 1
fi
ok "Python $(python3 --version 2>&1)"

# ─── 2. VERIFICAR DEPENDENCIAS ──────────────────────────────────────
echo -e "\n${W}── 2/6 Verificando dependencias...${N}"
MISSING=""
python3 -c "import fastapi" 2>/dev/null && ok "fastapi" || MISSING="$MISSING fastapi"
python3 -c "import uvicorn" 2>/dev/null && ok "uvicorn" || MISSING="$MISSING uvicorn"
python3 -c "import httpx" 2>/dev/null && ok "httpx" || MISSING="$MISSING httpx"
python3 -c "import psutil" 2>/dev/null && ok "psutil" || MISSING="$MISSING psutil"
python3 -c "from Crypto.Cipher import AES" 2>/dev/null && ok "pycryptodome" || MISSING="$MISSING pycryptodome"

if [ -n "$MISSING" ]; then
    warn "Faltan:$MISSING — instalando..."
    pip install -q $MISSING 2>&1 | tail -3
    ok "Dependencias instaladas"
fi

# ─── 3. .ENV ────────────────────────────────────────────────────────
echo -e "\n${W}── 3/6 Configuración .env...${N}"
if [ ! -f "$ROOT/.env" ]; then
    info "Creando .env por primera vez..."
    API_KEY=$(openssl rand -hex 24)
    cat > "$ROOT/.env" << EOF
REDTEAM_API_KEY=${API_KEY}
HOST=0.0.0.0
PORT=${PORT}
ALLOWED_ORIGINS=http://localhost:${PORT},http://127.0.0.1:${PORT}
EOF
    chmod 600 "$ROOT/.env"
    ok ".env creado. API Key: ${API_KEY:0:8}..."
    echo -e "  ${Y}GUARDA TU KEY: ${API_KEY}${N}"
else
    ok ".env existe"
fi

# Cargar .env
set -a
. "$ROOT/.env" 2>/dev/null || true
set +a

# ─── 4. LIBERAR PUERTOS ─────────────────────────────────────────────
echo -e "\n${W}── 4/6 Liberando puertos...${N}"
for port in $PORT $GATEWAY_PORT $COMMANDER_PORT; do
    pid=$(lsof -t -i :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        warn "Puerto :$port ocupado (PID $pid) — liberando"
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
done
ok "Puertos libres"

# ─── 5. GATEWAY MESH (opcional) ─────────────────────────────────────
GATEWAY_PID=""
if [ "$START_GATEWAY" = "1" ]; then
    echo -e "\n${W}── 5/6 Gateway Mesh...${N}"
    if [ -f "$ROOT/gateway/mesh_server.py" ]; then
        info "Iniciando gateway en :$GATEWAY_PORT..."
        (
            cd "$ROOT/gateway"
            PORT="$GATEWAY_PORT" python3 mesh_server.py
        ) > "$ROOT/sourceseal-gateway.log" 2>&1 &
        GATEWAY_PID=$!

        GATEWAY_READY=0
        for i in $(seq 1 10); do
            if curl -fsS "http://127.0.0.1:$GATEWAY_PORT/health" >/dev/null 2>&1; then
                GATEWAY_READY=1
                break
            fi
            kill -0 "$GATEWAY_PID" 2>/dev/null || break
            sleep 1
        done

        if [ "$GATEWAY_READY" = "1" ]; then
            ok "Gateway OK en :$GATEWAY_PORT"
        else
            warn "Gateway no disponible — continuando sin él"
            GATEWAY_PID=""
        fi
    else
        warn "gateway/mesh_server.py no encontrado — saltando"
    fi
else
    echo -e "\n${W}── 5/6 Gateway deshabilitado${N}"
fi

# ─── 6. ARRANCAR DASHBOARD PRINCIPAL ────────────────────────────────
echo -e "\n${W}── 6/6 Arrancando Dashboard...${N}"

if [ ! -f "$ROOT/redteam/scripts/dashboard_server.py" ]; then
    fail "dashboard_server.py no encontrado"
    fail "Ejecuta: bash termux_sync.sh para sincronizar el repo"
    exit 1
fi

cd "$ROOT/redteam/scripts"

# Arrancar backend
python3 dashboard_server.py > "$ROOT/sourceseal-backend.log" 2>&1 &
BACKEND_PID=$!

echo -e "\n${G}╔══════════════════════════════════════════════════╗${N}"
echo -e "${G}║  SOURCESEAL ARRANCANDO...                        ║${N}"
echo -e "${G}║                                                  ║${N}"
echo -e "${G}║  Dashboard:  http://localhost:${PORT}             ║${N}"
if [ -n "$GATEWAY_PID" ]; then
echo -e "${G}║  Gateway:    http://localhost:${GATEWAY_PORT}      ║${N}"
fi
echo -e "${G}║                                                  ║${N}"
# Obtener IP WiFi
WIFI_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || true)
if [ -n "$WIFI_IP" ]; then
echo -e "${G}║  WiFi:       http://${WIFI_IP}:${PORT}    ║${N}"
fi
echo -e "${G}║                                                  ║${N}"
echo -e "${G}║  Logs:  sourceseal-backend.log                   ║${N}"
echo -e "${G}║  Ctrl+C para detener                             ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
echo ""

# Esperar a que el backend esté listo
BACKEND_OK=0
for i in $(seq 1 15); do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
        BACKEND_OK=1
        ok "Backend online en :$PORT"
        break
    fi
    kill -0 "$BACKEND_PID" 2>/dev/null || break
    sleep 1
done

if [ "$BACKEND_OK" = "0" ]; then
    fail "Backend no respondió en 15s. Revisa el log:"
    tail -20 "$ROOT/sourceseal-backend.log" 2>/dev/null
    exit 1
fi

# ─── CLEANUP AL SALIR ───────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${Y}[!] Deteniendo SOURCESEAL...${N}"
    kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "$GATEWAY_PID" ] && kill "$GATEWAY_PID" 2>/dev/null || true
    pkill -f "$ROOT/redteam/scripts/dashboard_server.py" 2>/dev/null || true
    pkill -f "$ROOT/gateway/mesh_server.py" 2>/dev/null || true
    command -v termux-wake-release >/dev/null 2>&1 && termux-wake-release || true
    echo -e "${G}[OK] Sistema detenido${N}"
}
trap cleanup EXIT INT TERM

# ─── MANTENER PROCESO VIVO ──────────────────────────────────────────
echo -e "${C}Sistema activo. Presiona Ctrl+C para detener.${N}"
echo ""

# Mostrar logs en vivo
tail -f "$ROOT/sourceseal-backend.log" 2>/dev/null || wait "$BACKEND_PID"
