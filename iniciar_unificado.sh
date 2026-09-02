#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL UNIFIED LAUNCHER — Red-team-tauri + Commander + PHANTOM
#
#   :8001 — Dashboard FastAPI
#            └── Commander in-process (/api/commander/*)
#   :8002 — GHOST HUNTER PHANTOM Master
#
# Commander no necesita un servidor ni un puerto adicional.
# v2: auth_bootstrap antes del backend — .env es la única fuente de verdad
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

# -- 0. Sincronizar hash de password desde .env si falta --
if [ -f "$ROOT/auth_bootstrap.py" ]; then
    echo "[unified] Sincronizando credenciales desde .env..."
    (cd "$ROOT" && python3 auth_bootstrap.py --verbose) || true
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
NEXUS_PID=""
CONTROLLER_PID=""
WARROOM_PID=""
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
    [ -n "$NEXUS_PID" ] && kill "$NEXUS_PID" 2>/dev/null || true
    [ -n "$CONTROLLER_PID" ] && kill "$CONTROLLER_PID" 2>/dev/null || true
    pkill -f "$ROOT/nexus_omni_v9.py" 2>/dev/null || true
    pkill -f "$HOME/sourceseal_controller.py" 2>/dev/null || true
    [ -n "$WARROOM_PID" ] && kill "$WARROOM_PID" 2>/dev/null || true
    pkill -f "$ROOT/warroom.py" 2>/dev/null || true
    echo "[unified] Sistema detenido"
}
trap 'cleanup; exit 0' SIGTERM SIGINT

# ─── 0.a Preflight: verificar pycryptodome (reemplaza cryptography) ───
ensure_pycryptodome() {
    if "$PYTHON_BIN" -c "from Crypto.Cipher import AES" >/dev/null 2>&1; then
        return 0
    fi
    echo "[unified][preflight] pycryptodome no importa; instalando..."
    "$PYTHON_BIN" -m pip install pycryptodome >/dev/null 2>&1 || true
    if "$PYTHON_BIN" -c "from Crypto.Cipher import AES" >/dev/null 2>&1; then
        echo "[unified][preflight] ✅ pycryptodome instalado"
        return 0
    fi
    if command -v pkg >/dev/null 2>&1; then
        pkg install -y python-pycryptodome >/dev/null 2>&1 || true
    fi
    if "$PYTHON_BIN" -c "from Crypto.Cipher import AES" >/dev/null 2>&1; then
        echo "[unified][preflight] ✅ pycryptodome instalado vía pkg"
        return 0
    fi
    echo "[unified][preflight][ERROR] No pude instalar pycryptodome." >&2
    return 1
}
ensure_pycryptodome || exit 1

# ─── 0.b Preflight: liberar puertos ocupados por instancias previas ──
free_port() {
    local port="$1"
    local pids=""
    if command -v fuser >/dev/null 2>&1; then
        pids="$(fuser -n tcp "$port" 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
        pids="$(ss -H -ltnp "sport = :$port" 2>/dev/null \
            | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
    fi
    if [ -n "$pids" ]; then
        echo "[unified][preflight] Liberando puerto $port (PIDs: $pids)"
        # shellcheck disable=SC2086
        kill -9 $pids 2>/dev/null || true
        sleep 1
    fi
}
free_port "$PORT"
free_port "$MASTER_PORT"

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

# ─── 0.c Preflight: verificar .env antes de arrancar (fail-closed) ──
ENV_FILE="$ROOT/.env"
_fail_lockout() {
    echo ""
    echo "[unified][LOCKOUT-PREVENT] ═══════════════════════════════════"
    echo "[unified][LOCKOUT-PREVENT]  DETENIDO: $1"
    echo "[unified][LOCKOUT-PREVENT]  No se arrancó ningún servicio."
    echo "[unified][LOCKOUT-PREVENT]  No se regeneró ninguna credencial."
    echo "[unified][LOCKOUT-PREVENT] ────────────────────────────────────"
    echo "[unified][LOCKOUT-PREVENT]  Para recuperar:"
    echo "[unified][LOCKOUT-PREVENT]    bash scripts/restore_env.sh"
    echo "[unified][LOCKOUT-PREVENT]  o si tienes respaldo manual:"
    echo "[unified][LOCKOUT-PREVENT]    bash control_claves.sh restore"
    echo "[unified][LOCKOUT-PREVENT]  o definir desde cero:"
    echo "[unified][LOCKOUT-PREVENT]    bash control_claves.sh set"
    echo "[unified][LOCKOUT-PREVENT] ═══════════════════════════════════"
    exit 1
}

if [ ! -f "$ENV_FILE" ]; then
    _fail_lockout ".env NO EXISTE en $ENV_FILE"
fi

# Verificar que las 3 variables críticas tienen valor
_ENV_MISSING=""
for v in ADMIN_PASSWORD NEXUS_PASS REDTEAM_API_KEY; do
    _val="$(grep "^${v}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "\047\042" || true)"
    if [ -z "$_val" ]; then
        _ENV_MISSING="$_ENV_MISSING $v"
    fi
done

if [ -n "$_ENV_MISSING" ]; then
    _fail_lockout "Variables vacías o ausentes:$_ENV_MISSING"
fi

# Verificar permisos 600 (warn, no abortar — algunos dispositivos no soportan chmod preciso)
_ENV_PERMS="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%A' "$ENV_FILE" 2>/dev/null || echo '?')"
if [ "$_ENV_PERMS" != "600" ]; then
    echo "[unified][WARN] .env permisos=$_ENV_PERMS (recomendado 600). Ejecuta: chmod 600 $ENV_FILE"
fi

echo "[unified] ✅ Preflight .env: 3 variables presentes, permisos=$_ENV_PERMS"

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
        echo "[unified][WARN] Commander no respondió; Dashboard continua activo"
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
echo "╔══════════════════════════════════════════════════════╗"
echo "║  SOURCESEAL UNIFIED — Sistema activo                   ║"
echo "║  Dashboard:  http://127.0.0.1:$PORT                    ║"
echo "║  Commander:  http://127.0.0.1:$PORT/api/commander/health║"
echo "║  PHANTOM:    http://127.0.0.1:$MASTER_PORT/api/status  ║"
echo "║  Caza:       POST :$MASTER_PORT/api/hunt/start          ║"
echo "║  Nexus:      http://127.0.0.1:8004                      ║"
echo "║  Controller: http://127.0.0.1:8005/api/status           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "[unified] Presiona Ctrl+C para detener todo."

# ─── 5. Nexus Omni-Sentient :8004 (idempotente) ───────────
NEXUS_PID=""
if [ -f "$ROOT/nexus_omni_v9.py" ]; then
    # Verificar si ya está vivo en 8004
    NEXUS_UP=0
    NCODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:8004/" 2>/dev/null || true)"
    if [ "$NCODE" != "000" ] && [ -n "$NCODE" ]; then
        echo "[unified] ✅ Nexus ya activo en :8004 (HTTP $NCODE) — no se duplica"
        NEXUS_UP=1
    fi
    if [ "$NEXUS_UP" = "0" ]; then
        echo "[unified] Arrancando Nexus Omni-Sentient en :8004..."
        cd "$ROOT"
        NEXUS_PORT=8004 nohup "$PYTHON_BIN" nexus_omni_v9.py > "$HOME/nexus.log" 2>&1 &
        NEXUS_PID=$!
        echo "[unified] Nexus PID: $NEXUS_PID"
        # Esperar que responda (cualquier HTTP code significa que está arriba)
        for i in $(seq 1 20); do
            NCODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:8004/" 2>/dev/null || true)"
            if [ "$NCODE" != "000" ] && [ -n "$NCODE" ]; then
                echo "[unified] ✅ Nexus listo en :8004 (HTTP $NCODE)"
                NEXUS_UP=1
                break
            fi
            sleep 1
        done
        if [ "$NEXUS_UP" = "0" ]; then
            echo "[unified][WARN] Nexus no respondió en 20s — continua el resto del sistema"
        fi
    fi
else
    echo "[unified][INFO] nexus_omni_v9.py no encontrado — saltando Nexus"
fi

# ─── 6. SourceSeal Controller :8005 (idempotente) ────────
CONTROLLER_PID=""
if [ -f "$HOME/sourceseal_controller.py" ]; then
    # Verificar si ya está vivo en 8005
    CTRL_UP=0
    CCODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:8005/api/status" 2>/dev/null || true)"
    if [ "$CCODE" != "000" ] && [ -n "$CCODE" ]; then
        echo "[unified] ✅ Controller ya activo en :8005 (HTTP $CCODE) — no se duplica"
        CTRL_UP=1
    fi
    if [ "$CTRL_UP" = "0" ]; then
        echo "[unified] Arrancando SourceSeal Controller en :8005..."
        # .env ya está cargado al inicio del script
        cd "$HOME"
        nohup "$PYTHON_BIN" "$HOME/sourceseal_controller.py" > "$HOME/controller.log" 2>&1 &
        CONTROLLER_PID=$!
        echo "[unified] Controller PID: $CONTROLLER_PID"
        for i in $(seq 1 15); do
            CCODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:8005/api/status" 2>/dev/null || true)"
            if [ "$CCODE" != "000" ] && [ -n "$CCODE" ]; then
                echo "[unified] ✅ Controller listo en :8005 (HTTP $CCODE)"
                CTRL_UP=1
                break
            fi
            sleep 1
        done
        if [ "$CTRL_UP" = "0" ]; then
            echo "[unified][WARN] Controller no respondió en 15s — continua el resto del sistema"
        fi
    fi
else
    echo "[unified][INFO] ~/sourceseal_controller.py no encontrado — saltando Controller"
fi

cd "$ROOT"

# ─── 7. Seal IA (orquestador de operaciones continuas) ────
SEAL_ENABLED_VAL="$(grep -q '^SEAL_ENABLED=1' "$ENV_FILE" 2>/dev/null && echo 1 || echo 0)"
if [ "$SEAL_ENABLED_VAL" = "1" ] && [ -f "$ROOT/seal/orchestrator/seal_orchestrator.py" ]; then
    echo "[unified] Arrancando Seal IA..."
    SEAL_PID_FILE="$HOME/.seal_orchestrator.pid"
    # Idempotente: si ya está corriendo, no duplicar
    if [ -f "$SEAL_PID_FILE" ] && kill -0 "$(cat "$SEAL_PID_FILE" 2>/dev/null)" 2>/dev/null; then
        echo "[unified] ✅ Seal IA ya activo (PID $(cat "$SEAL_PID_FILE")) — no se duplica"
    else
        SEAL_NETWORK_VAL="$(grep '^SEAL_NETWORK=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d "'\"" || echo "192.168.1.0/24")"
        cd "$ROOT"
        nohup "$PYTHON_BIN" "$ROOT/seal/orchestrator/seal_orchestrator.py" --start > "$HOME/seal_ia.log" 2>&1 &
        SEAL_PID=$!
        echo "$SEAL_PID" > "$SEAL_PID_FILE"
        echo "[unified] Seal IA PID: $SEAL_PID — log: ~/seal_ia.log"
        sleep 1
        if kill -0 "$SEAL_PID" 2>/dev/null; then
            echo "[unified] ✅ Seal IA arrancado"
        else
            echo "[unified][WARN] Seal IA terminó de inmediato — ver ~/seal_ia.log"
            tail -5 "$HOME/seal_ia.log" 2>/dev/null
        fi
    fi
else
    echo "[unified][INFO] Seal IA desactivado (SEAL_ENABLED≠1 o falta seal/orchestrator/seal_orchestrator.py)"
fi

# ─── 8. War Room :8010 (idempotente, opcional) ──────────
WARROOM_PID=""
WARROOM_ENABLED="${WARROOM_ENABLED:-1}"
if [ "$WARROOM_ENABLED" = "1" ] && [ -f "$ROOT/warroom.py" ]; then
    WR_UP=0
    WRCODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:8010/api/health" 2>/dev/null || true)"
    if [ "$WRCODE" != "000" ] && [ -n "$WRCODE" ]; then
        echo "[unified] ✅ War Room ya activo en :8010 (HTTP $WRCODE) — no se duplica"
        WR_UP=1
    fi
    if [ "$WR_UP" = "0" ]; then
        echo "[unified] Arrancando War Room en :8010..."
        nohup "$PYTHON_BIN" "$ROOT/warroom.py" > "$HOME/.warroom.log" 2>&1 &
        WARROOM_PID=$!
        echo "[unified] War Room PID: $WARROOM_PID — log: ~/.warroom.log"
        for i in $(seq 1 10); do
            WRCODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:8010/api/health" 2>/dev/null || true)"
            if [ "$WRCODE" != "000" ] && [ -n "$WRCODE" ]; then
                echo "[unified] ✅ War Room listo en :8010"
                WR_UP=1
                break
            fi
            sleep 1
        done
        if [ "$WR_UP" = "0" ]; then
            echo "[unified][WARN] War Room no respondió en 10s — continua el resto del sistema"
        fi
    fi
else
    echo "[unified][INFO] War Room desactivado (WARROOM_ENABLED≠1 o falta warroom.py)"
fi

cd "$ROOT"

# ── Sol API + Daemon + Telegram Bridge (idempotente) ──
pgrep -f sol_api.py        >/dev/null || nohup python3 "$ROOT/sol_api.py" >"$HOME/.sol/sol_api.log" 2>&1 &
pgrep -f sol_daemon.py     >/dev/null || nohup python3 "$ROOT/sol_daemon.py" >"$HOME/.sol/daemon.log" 2>&1 &
pgrep -f sol_telegram_bridge >/dev/null || nohup python3 "$ROOT/sol_telegram_bridge.py" >"$HOME/.sol/tg.log" 2>&1 &

# Mantener vivos los procesos. Si uno cae, no dejamos servicios huérfanos.
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
