#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL TODO — Arranque unificado de los 3 servicios
#   :8001 Red-team-tauri Dashboard (dashboard_server.py)
#   :8002 GHOST HUNTER PHANTOM Master (master.py + node.py)
#   :8003 COMMANDER Dashboard (commander_server.py)
# Un solo comando. Un solo Ctrl+C para detener todo.
# =====================================================================

# Colores
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m'
P='\033[0;35m' B='\033[1;34m' N='\033[0m'

# Detectar raíz (asume que Red-team-tauri y commander son carpetas hermanas)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detectar dónde está cada repo
RT_DIR=""
CMD_DIR=""

# Si el script está dentro de Red-team-tauri
if [ -f "$SCRIPT_DIR/redteam/scripts/dashboard_server.py" ]; then
    RT_DIR="$SCRIPT_DIR"
    CMD_DIR="$SCRIPT_DIR/../commander"
elif [ -f "$SCRIPT_DIR/commander_server.py" ]; then
    CMD_DIR="$SCRIPT_DIR"
    RT_DIR="$SCRIPT_DIR/../Red-team-tauri"
else
    # Buscar en el home
    for d in "$HOME" "$HOME/storage" "$HOME/projects" "$(pwd)"; do
        if [ -f "$d/Red-team-tauri/redteam/scripts/dashboard_server.py" ]; then
            RT_DIR="$d/Red-team-tauri"
            CMD_DIR="$d/commander"
            break
        fi
        if [ -f "$d/redteam/scripts/dashboard_server.py" ]; then
            RT_DIR="$d"
            CMD_DIR="$d/../commander"
            break
        fi
    done
fi

echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  🌹 SOURCESEAL TODO — Arranque unificado de 3 servicios    ║${N}"
echo -e "${C}╠══════════════════════════════════════════════════════════╣${N}"
echo -e "${C}║  :8001  Red-team-tauri Dashboard                         ║${N}"
echo -e "${C}║  :8002  GHOST HUNTER PHANTOM Master + Node               ║${N}"
echo -e "${C}║  :8003  COMMANDER Dashboard                              ║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""

# Verificar que encontramos los repos
if [ -z "$RT_DIR" ] || [ ! -f "$RT_DIR/redteam/scripts/dashboard_server.py" ]; then
    echo -e "${R}[error] No se encontró Red-team-tauri${N}"
    echo -e "${Y}        Esperado: redteam/scripts/dashboard_server.py${N}"
    echo -e "${Y}        Pone este script en la raíz de Red-team-tauri o en una carpeta que contenga ambos repos.${N}"
    exit 1
fi

echo -e "${G}[ok] Red-team-tauri: $RT_DIR${N}"
if [ -d "$CMD_DIR" ] && [ -f "$CMD_DIR/commander_server.py" ]; then
    echo -e "${G}[ok] COMMANDER: $CMD_DIR${N}"
else
    echo -e "${Y}[warn] COMMANDER no encontrado en $CMD_DIR${N}"
    echo -e "${Y}       :8003 no arrancará. Solo :8001 + :8002${N}"
    CMD_DIR=""
fi

# ─── Cleanup de procesos previos ─────────────────────────
echo ""
echo -e "${Y}[cleanup] Matando procesos previos...${N}"
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
pkill -f "commander_server.py" 2>/dev/null || true
sleep 2

# ─── 1. Red-team-tauri (:8001) ───────────────────────────
echo ""
echo -e "${C}━━━ 1/3 — Red-team-tauri Dashboard (:8001) ━━━━━━━━━━━━━${N}"

cd "$RT_DIR"

# Build frontend (no-fatal)
if [ -d "tauri-frontend" ]; then
    cd tauri-frontend
    if [ ! -d "node_modules" ]; then
        echo -e "${Y}[rt] Instalando dependencias Node...${N}"
        npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -3 || true
    fi
    echo -e "${Y}[rt] Build frontend...${N}"
    npm run build 2>&1 | tail -5 || echo -e "${Y}[rt] Build falló — usando dist/ existente${N}"
    cd "$RT_DIR"
fi

# Copiar dist si existe
if [ -d "tauri-frontend/dist" ] && [ -d "redteam/scripts" ]; then
    cp -r tauri-frontend/dist/. redteam/scripts/dist/ 2>/dev/null || true
fi

echo -e "${Y}[rt] Arrancando backend en :8001...${N}"
cd "$RT_DIR/redteam/scripts"
PORT=8001 HOST=0.0.0.0 PYTHONUNBUFFERED=1 python3 dashboard_server.py &
RT_PID=$!
echo -e "${G}[rt] Dashboard PID: $RT_PID${N}"

# Esperar a que esté listo
RT_OK=false
for i in $(seq 1 25); do
    if ! kill -0 $RT_PID 2>/dev/null; then
        echo -e "${R}[rt] El proceso murió. Revisa los logs arriba.${N}"
        break
    fi
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        echo -e "${G}[rt] ✅ Dashboard listo en :8001${N}"
        RT_OK=true
        break
    fi
    sleep 1
done
if [ "$RT_OK" = false ] && kill -0 $RT_PID 2>/dev/null; then
    echo -e "${Y}[rt] ⚠️ No respondió en 25s pero el proceso vive — continuando${N}"
fi

cd "$RT_DIR"

# ─── 2. GHOST HUNTER PHANTOM (:8002) ─────────────────────
echo ""
echo -e "${P}━━━ 2/3 — GHOST HUNTER PHANTOM (:8002) ━━━━━━━━━━━━━━━${N}"

PHANTOM_DIR="$RT_DIR/ghost_hunter_phantom"
PHANTOM_OK=false

if [ -d "$PHANTOM_DIR" ] && [ -f "$PHANTOM_DIR/master.py" ]; then
    cd "$PHANTOM_DIR"
    echo -e "${Y}[phantom] Arrancando Master en :8002...${N}"
    BACKEND_API="http://localhost:8001" MASTER_PORT=8002 python3 master.py &
    PHANTOM_PID=$!
    echo -e "${G}[phantom] Master PID: $PHANTOM_PID${N}"
    sleep 2

    echo -e "${Y}[phantom] Arrancando Node worker...${N}"
    NODE_ID="phantom_node_1" MASTER_URL="http://localhost:8002" BACKEND_API="http://localhost:8001" python3 node.py &
    NODE_PID=$!
    echo -e "${G}[phantom] Node PID: $NODE_PID${N}"

    # Verificar master
    for i in $(seq 1 10); do
        HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8002/api/status" 2>/dev/null || echo "000")
        if [ "$HTTP" = "200" ]; then
            echo -e "${G}[phantom] ✅ Master listo en :8002${N}"
            PHANTOM_OK=true
            break
        fi
        sleep 1
    done
    if [ "$PHANTOM_OK" = false ]; then
        echo -e "${Y}[phantom] ⚠️ Master no respondió pero el proceso vive${N}"
    fi
    cd "$RT_DIR"
else
    echo -e "${Y}[phantom] ⚠️ ghost_hunter_phantom/ no encontrado — saltando :8002${N}"
    PHANTOM_PID=""
    NODE_PID=""
fi

# ─── 3. COMMANDER Dashboard (:8003) ─────────────────────
echo ""
echo -e "${B}━━━ 3/3 — COMMANDER Dashboard (:8003) ━━━━━━━━━━━━━━━━━${N}"

CMD_OK=false

if [ -n "$CMD_DIR" ] && [ -f "$CMD_DIR/commander_server.py" ]; then
    cd "$CMD_DIR"
    echo -e "${Y}[commander] Arrancando dashboard en :8003...${N}"
    COMMANDER_PORT=8003 BACKEND_API="http://localhost:8001" python3 commander_server.py &
    CMD_PID=$!
    echo -e "${G}[commander] PID: $CMD_PID${N}"

    for i in $(seq 1 15); do
        HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8003/api/health" 2>/dev/null || echo "000")
        if [ "$HTTP" = "200" ]; then
            echo -e "${G}[commander] ✅ Dashboard listo en :8003${N}"
            CMD_OK=true
            break
        fi
        sleep 1
    done
    if [ "$CMD_OK" = false ]; then
        echo -e "${Y}[commander] ⚠️ No respondió pero el proceso vive${N}"
    fi
    cd "$RT_DIR"
else
    echo -e "${Y}[commander] ⚠️ commander_server.py no encontrado — saltando :8003${N}"
    CMD_PID=""
fi

# ─── Estado final ────────────────────────────────────────
echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  🌹 SOURCESEAL TODO — Sistema activo                       ║${N}"
echo -e "${C}╠══════════════════════════════════════════════════════════╣${N}"

if $RT_OK; then
    echo -e "${G}║  ✅ :8001 Red-team-tauri  http://localhost:8001          ║${N}"
else
    echo -e "${Y}║  ⚠️  :8001 Red-team-tauri (verificando...)               ║${N}"
fi

if $PHANTOM_OK; then
    echo -e "${G}║  ✅ :8002 GHOST PHANTOM   http://localhost:8002/api/status║${N}"
else
    echo -e "${Y}║  ⚠️  :8002 GHOST PHANTOM (opcional)                      ║${N}"
fi

if $CMD_OK; then
    echo -e "${G}║  ✅ :8003 COMMANDER       http://localhost:8003          ║${N}"
else
    echo -e "${Y}║  ⚠️  :8003 COMMANDER (opcional)                           ║${N}"
fi

echo -e "${C}║                                                          ║${N}"
echo -e "${C}║  PIDs: RT=$RT_PID Phantom=$PHANTOM_PID Cmd=$CMD_PID       ║${N}"
echo -e "${C}║  Ctrl+C detiene TODO                                      ║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""

# ─── Cleanup ────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${R}[shutdown] Apagando todo...${N}"
    kill $RT_PID 2>/dev/null || true
    [ -n "$PHANTOM_PID" ] && kill $PHANTOM_PID 2>/dev/null || true
    [ -n "$NODE_PID" ] && kill $NODE_PID 2>/dev/null || true
    [ -n "$CMD_PID" ] && kill $CMD_PID 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    pkill -f "commander_server.py" 2>/dev/null || true
    echo -e "${G}[shutdown] ✅ Todo apagado. Hasta pronto 🌹${N}"
    exit 0
}
trap cleanup SIGTERM SIGINT

# Mantener vivo
echo -e "${Y}Presiona Ctrl+C para detener todo.${N}"
echo ""
wait
