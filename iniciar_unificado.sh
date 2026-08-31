#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL UNIFIED LAUNCHER — Red-team-tauri + Commander + PHANTOM
#
#   :8001 — Dashboard FastAPI
#            └── Commander in-process (/api/commander/*)
#   :8002 — GHOST HUNTER PHANTOM Master
#
# Commander no necesita un servidor ni un puerto adicional.
# =====================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Permite ejecutar este archivo directamente, sin pasar por otro launcher.
if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$ROOT/.env"
    set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8001}"
MASTER_PORT="${MASTER_PORT:-8002}"
COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"
START_COMMANDER="${START_COMMANDER:-1}"
export COMMANDER_DIR

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "[unified][ERROR] Falta el comando requerido: $1" >&2
        exit 1
    }
}

require_command "$PYTHON_BIN"
require_command curl
[ -f "$ROOT/redteam/scripts/dashboard_server.py" ] || {
    echo "[unified][ERROR] Falta redteam/scripts/dashboard_server.py" >&2
    exit 1
}
[ -f "$ROOT/ghost_hunter_phantom/master.py" ] || {
    echo "[unified][ERROR] Falta ghost_hunter_phantom/master.py" >&2
    exit 1
}
[ -f "$ROOT/ghost_hunter_phantom/node.py" ] || {
    echo "[unified][ERROR] Falta ghost_hunter_phantom/node.py" >&2
    exit 1
}

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  SOURCESEAL UNIFIED — Iniciando sistema completo       ║"
echo "║  :$PORT Dashboard  :$MASTER_PORT GHOST PHANTOM          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

DASHBOARD_PID=""
MASTER_PID=""
NODE_PID=""
STOPPING=0

cleanup() {
    [ "$STOPPING" = "1" ] && return 0
    STOPPING=1
    echo ""
    echo "[unified] Apagando sistema..."
    [ -n "$DASHBOARD_PID" ] && kill "$DASHBOARD_PID" 2>/dev/null || true
    [ -n "$MASTER_PID" ] && kill "$MASTER_PID" 2>/dev/null || true
    [ -n "$NODE_PID" ] && kill "$NODE_PID" 2>/dev/null || true
    pkill -f "$ROOT/redteam/scripts/dashboard_server.py" 2>/dev/null || true
    pkill -f "$ROOT/ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "$ROOT/ghost_hunter_phantom/node.py" 2>/dev/null || true
    echo "[unified] Sistema detenido"
}
trap 'cleanup; exit 0' SIGTERM SIGINT

echo "[unified] Limpiando procesos previos..."
pkill -f "$ROOT/redteam/scripts/dashboard_server.py" 2>/dev/null || true
pkill -f "$ROOT/ghost_hunter_phantom/master.py" 2>/dev/null || true
pkill -f "$ROOT/ghost_hunter_phantom/node.py" 2>/dev/null || true
sleep 1

wait_for_http() {
    local pid="$1"
    local url="$2"
    local label="$3"
    local attempts="$4"
    local code=""

    for i in $(seq 1 "$attempts"); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "[unified][ERROR] $label terminó antes de responder." >&2
            cleanup
            exit 1
        fi
        code="$(curl -sS -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || true)"
        if [ "$code" = "200" ]; then
            echo "[unified] ✅ $label listo"
            return 0
        fi
        sleep 1
    done

    echo "[unified][ERROR] $label no respondió en ${attempts}s (último HTTP: ${code:-000})." >&2
    cleanup
    exit 1
}

# ─── 1. Dashboard backend ─────────────────────────────────
echo "[unified] Arrancando Dashboard en :$PORT..."
cd "$ROOT/redteam/scripts"
PORT="$PORT" HOST="${HOST:-0.0.0.0}" COMMANDER_DIR="$COMMANDER_DIR" \
    PYTHONUNBUFFERED=1 "$PYTHON_BIN" dashboard_server.py &
DASHBOARD_PID=$!
echo "[unified] Dashboard PID: $DASHBOARD_PID"
wait_for_http "$DASHBOARD_PID" "http://127.0.0.1:$PORT/api/health" "Dashboard :$PORT" 30

cd "$ROOT"

# ─── 2. Commander in-process ──────────────────────────────
if [ "$START_COMMANDER" = "0" ]; then
    echo "[unified] Commander desactivado por START_COMMANDER=0"
elif [ -f "$COMMANDER_DIR/commander.py" ]; then
    echo "[unified] Verificando Commander integrado..."
    COMMANDER_AUTH=()
    if [ -n "${REDTEAM_API_KEY:-}" ]; then
        COMMANDER_AUTH=(-H "Authorization: Bearer ${REDTEAM_API_KEY}")
    fi
    COMMANDER_READY=0
    for i in $(seq 1 15); do
        HTTP_CODE="$(curl -sS -o /dev/null -w "%{http_code}" \
            "${COMMANDER_AUTH[@]}" \
            "http://127.0.0.1:$PORT/api/commander/health" 2>/dev/null || true)"
        if [ "$HTTP_CODE" = "200" ]; then
            echo "[unified] ✅ Commander integrado listo en :$PORT/api/commander/*"
            COMMANDER_READY=1
            break
        fi
        sleep 1
    done
    if [ "$COMMANDER_READY" != "1" ]; then
        echo "[unified][WARN] Commander no respondió; Dashboard continúa activo"
    fi
else
    echo "[unified][WARN] Commander no encontrado: $COMMANDER_DIR"
    echo "[unified] /api/commander/* permanecerá desactivado"
fi

# ─── 3. GHOST HUNTER PHANTOM Master ───────────────────────
echo "[unified] Arrancando GHOST PHANTOM Master en :$MASTER_PORT..."
cd "$ROOT/ghost_hunter_phantom"
BACKEND_API="http://127.0.0.1:$PORT" MASTER_PORT="$MASTER_PORT" \
    "$PYTHON_BIN" master.py &
MASTER_PID=$!
echo "[unified] Master PID: $MASTER_PID"
wait_for_http "$MASTER_PID" "http://127.0.0.1:$MASTER_PORT/api/status" \
    "PHANTOM Master :$MASTER_PORT" 20

# ─── 4. PHANTOM Node ──────────────────────────────────────
echo "[unified] Arrancando PHANTOM Node worker..."
NODE_ID="phantom_node_1" MASTER_URL="http://127.0.0.1:$MASTER_PORT" \
    BACKEND_API="http://127.0.0.1:$PORT" "$PYTHON_BIN" node.py &
NODE_PID=$!
echo "[unified] Node PID: $NODE_PID"
sleep 2
if ! kill -0 "$NODE_PID" 2>/dev/null; then
    echo "[unified][ERROR] PHANTOM Node terminó al iniciar." >&2
    cleanup
    exit 1
fi

cd "$ROOT"
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  SOURCESEAL UNIFIED — Sistema activo                   ║"
echo "║  Dashboard:  http://127.0.0.1:$PORT                    ║"
echo "║  Commander:  http://127.0.0.1:$PORT/api/commander/health║"
echo "║  PHANTOM:    http://127.0.0.1:$MASTER_PORT/api/status  ║"
echo "║  Caza:       POST :$MASTER_PORT/api/hunt/start          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "[unified] Presiona Ctrl+C para detener todo."

# Mantener vivos los tres procesos. Si uno cae, no dejamos servicios huérfanos.
while true; do
    if ! kill -0 "$DASHBOARD_PID" 2>/dev/null; then
        echo "[unified][ERROR] Dashboard terminó inesperadamente." >&2
        cleanup
        exit 1
    fi
    if ! kill -0 "$MASTER_PID" 2>/dev/null; then
        echo "[unified][ERROR] PHANTOM Master terminó inesperadamente." >&2
        cleanup
        exit 1
    fi
    if ! kill -0 "$NODE_PID" 2>/dev/null; then
        echo "[unified][ERROR] PHANTOM Node terminó inesperadamente." >&2
        cleanup
        exit 1
    fi
    sleep 2
done