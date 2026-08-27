#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL UNIFIED LAUNCHER — Red-team-tauri + GHOST HUNTER PHANTOM
# Arranca todo en simultáneo:
#   :8001 — Dashboard FastAPI (dashboard_server.py)
#   :8002 — GHOST HUNTER PHANTOM Master (master.py)
# =====================================================================

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"
COMMANDER_PORT="${COMMANDER_PORT:-8003}"
START_COMMANDER="${START_COMMANDER:-1}"
COMMANDER_PID=""

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
pkill -f "commander_server.py" 2>/dev/null || true
sleep 1

# ─── 1. Dashboard backend (:8001) ─────────────────────────
echo "[unified] Arrancando Dashboard en :8001..."
cd "$ROOT/redteam/scripts"
PORT=8001 python3 dashboard_server.py &
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

# ─── 2. COMMANDER Dashboard (:8003) ─────────────────────
if [ "$START_COMMANDER" != "0" ] && [ -f "$COMMANDER_DIR/commander_server.py" ]; then
    echo "[unified] Arrancando COMMANDER Dashboard en :$COMMANDER_PORT..."
    cd "$COMMANDER_DIR"
    COMMANDER_PORT="$COMMANDER_PORT" COMMANDER_HOST="0.0.0.0" BACKEND_API="http://localhost:8001" PYTHONUNBUFFERED=1 python3 commander_server.py &
    COMMANDER_PID=$!
    echo "[unified] Commander PID: $COMMANDER_PID"

    for i in $(seq 1 15); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$COMMANDER_PORT/api/health" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo "[unified] ✅ Commander listo en :$COMMANDER_PORT"
            break
        fi
        sleep 1
    done
else
    echo "[unified] ⚠️ Commander no encontrado o desactivado: $COMMANDER_DIR"
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
║  Commander:  http://localhost:8003/api/health         ║
echo "║  PHANTOM:    http://localhost:8002/api/status         ║"
echo "║  Caza:       POST :8002/api/hunt/start                ║"
echo "║  WS nodes:   ws://localhost:8002/ws/nodes             ║"
echo "║                                                       ║"
║  PIDs: Dashboard=$DASHBOARD_PID Commander=$COMMANDER_PID ║
║        Master=$MASTER_PID Node=$NODE_PID               ║
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
    [ -n "$COMMANDER_PID" ] && kill "$COMMANDER_PID" 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    pkill -f "commander_server.py" 2>/dev/null || true
    echo "[unified] ✅ Apagado completo"
    exit 0
}
trap cleanup SIGTERM SIGINT

# Mantener vivo
wait
