#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL UNIFIED LAUNCHER — Red-team-tauri + Commander + GHOST HUNTER PHANTOM
# Arranca todo en simultáneo:
#   :8001 — Dashboard FastAPI (dashboard_server.py)
#            └── COMMANDER in-process (/api/commander/*)
#   :8002 — GHOST HUNTER PHANTOM Master (master.py)
# =====================================================================

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"
START_COMMANDER="${START_COMMANDER:-1}"
export COMMANDER_DIR

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  SOURCESEAL UNIFIED — Iniciando sistema completo       ║"
echo "║  :8001 Dashboard  :8002 GHOST PHANTOM Master          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ─── Cleanup de procesos previos ─────────────────────────
echo "[unified] Limpiando procesos previos..."
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
sleep 1

# ─── 1. Dashboard backend (:8001) ─────────────────────────
echo "[unified] Arrancando Dashboard en :8001..."
cd "$ROOT/redteam/scripts"
PORT=8001 COMMANDER_DIR="$COMMANDER_DIR" PYTHONUNBUFFERED=1 python3 dashboard_server.py &
DASHBOARD_PID=$!
echo "[unified] Dashboard PID: $DASHBOARD_PID"

# Esperar a que el dashboard esté listo
for i in $(seq 1 20); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[unified] ✅ Dashboard listo en :8001"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "[unified] ⚠️  Dashboard no respondió tras 20s — continuando igual"
    fi
    sleep 1
done

cd "$ROOT"

# ─── 2. COMMANDER in-process (/api/commander/*) ──────────
if [ "$START_COMMANDER" = "0" ]; then
    echo "[unified] Commander desactivado por START_COMMANDER=0"
elif [ -f "$COMMANDER_DIR/commander.py" ]; then
    echo "[unified] Verificando COMMANDER integrado en :8001..."
    COMMANDER_AUTH=()
    if [ -n "${REDTEAM_API_KEY:-}" ]; then
        COMMANDER_AUTH=(-H "Authorization: Bearer ${REDTEAM_API_KEY}")
    fi
    COMMANDER_READY=0
    for i in $(seq 1 15); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            "${COMMANDER_AUTH[@]}" \
            "http://localhost:8001/api/commander/health" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo "[unified] ✅ Commander integrado listo en :8001/api/commander/*"
            COMMANDER_READY=1
            break
        fi
        sleep 1
    done
    if [ "$COMMANDER_READY" != "1" ]; then
        echo "[unified] ⚠️ Commander no respondió; Dashboard continúa activo"
    fi
else
    echo "[unified] ⚠️ Commander no encontrado: $COMMANDER_DIR"
    echo "[unified]    /api/commander/* permanecerá desactivado"
fi

cd "$ROOT"

# ─── 3. GHOST HUNTER PHANTOM Master (:8002) ───────────────
echo "[unified] Arrancando GHOST PHANTOM Master en :8002..."
cd "$ROOT/ghost_hunter_phantom"
BACKEND_API="http://localhost:8001" MASTER_PORT=8002 python3 master.py &
MASTER_PID=$!
echo "[unified] Master PID: $MASTER_PID"

# Esperar a que el master esté listo
for i in $(seq 1 15); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8002/api/status" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[unified] ✅ Master listo en :8002"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "[unified] ⚠️  Master no respondió tras 15s — continuando"
    fi
    sleep 1
done

# ─── 3. PHANTOM Node (1 worker) ──────────────────────────
echo "[unified] Arrancando PHANTOM Node worker..."
NODE_ID="phantom_node_1" MASTER_URL="http://localhost:8002" BACKEND_API="http://localhost:8001" python3 node.py &
NODE_PID=$!
echo "[unified] Node PID: $NODE_PID"

cd "$ROOT"

# ─── Estado final ────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  SOURCESEAL UNIFIED — Sistema activo                   ║"
echo "║                                                       ║"
echo "║  Dashboard:  http://localhost:8001                     ║"
echo "║  Commander:  http://localhost:8001/api/commander/health ║"
echo "║  PHANTOM:    http://localhost:8002/api/status         ║"
echo "║  Caza:       POST :8002/api/hunt/start                ║"
echo "║  WS nodes:   ws://localhost:8002/ws/nodes             ║"
echo "║                                                       ║"
echo "║  PIDs: Dashboard=$DASHBOARD_PID                     ║"
echo "║        Master=$MASTER_PID Node=$NODE_PID               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "[unified] Presiona Ctrl+C para detener todo."
echo ""

# ─── Cleanup al salir ────────────────────────────────────
cleanup() {
    echo ""
    echo "[unified] Apagando sistema..."
    kill $DASHBOARD_PID 2>/dev/null || true
    kill $MASTER_PID 2>/dev/null || true
    kill $NODE_PID 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    echo "[unified] ✅ Apagado completo"
    exit 0
}
trap cleanup SIGTERM SIGINT

# Mantener vivo
wait
