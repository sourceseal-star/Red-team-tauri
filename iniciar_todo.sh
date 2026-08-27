#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL — Arranque unificado (modelo Control Tower)
# Un solo proceso principal: Red-team-tauri Dashboard (:8001)
#   - COMMANDER está montado DENTRO del dashboard (/api/commander/*)
#   - GHOST PHANTOM (Master :8002 + Node) se arrancan desde el propio
#     dashboard vía Control Tower (botón Start) o con --with-phantom
# =====================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WITH_PHANTOM=false
[ "$1" = "--with-phantom" ] && WITH_PHANTOM=true

R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' N='\033[0m'

echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  🌹 SOURCESEAL — Arranque unificado (Control Tower)        ║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""

cd "$SCRIPT_DIR"

# ─── Cleanup previo ───────────────────────────────────────
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
sleep 1

# ─── Build frontend (no-fatal) ────────────────────────────
if [ -d "tauri-frontend" ]; then
    cd tauri-frontend
    if [ ! -d "node_modules" ]; then
        echo -e "${Y}[build] Instalando dependencias Node...${N}"
        npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -3 || true
    fi
    echo -e "${Y}[build] Compilando frontend...${N}"
    npm run build 2>&1 | tail -5 || echo -e "${Y}[build] ⚠️  Falló — usando dist/ existente${N}"
    cd "$SCRIPT_DIR"
fi
if [ -d "tauri-frontend/dist" ] && [ -d "redteam/scripts" ]; then
    mkdir -p redteam/scripts/dist
    cp -r tauri-frontend/dist/. redteam/scripts/dist/ 2>/dev/null || true
fi

# ─── Detectar COMMANDER (repo hermano) ───────────────────
if [ -f "../commander/commander.py" ]; then
    echo -e "${G}[commander] Detectado en ../commander — se montará automáticamente${N}"
    export COMMANDER_DIR="$(cd "$SCRIPT_DIR/../commander" && pwd)"
else
    echo -e "${Y}[commander] No encontrado como carpeta hermana — /api/commander/* quedará desactivado${N}"
    echo -e "${Y}            (esto es normal si no clonaste 'commander' junto a 'Red-team-tauri')${N}"
fi

# ─── Arrancar Dashboard (:8001) ───────────────────────────
echo ""
echo -e "${C}[dashboard] Arrancando en :8001...${N}"
cd "$SCRIPT_DIR/redteam/scripts"
PORT=8001 HOST=0.0.0.0 PYTHONUNBUFFERED=1 python3 dashboard_server.py &
RT_PID=$!
echo -e "${G}[dashboard] PID: $RT_PID${N}"

for i in $(seq 1 25); do
    if ! kill -0 $RT_PID 2>/dev/null; then
        echo -e "${R}[dashboard] El proceso murió. Revisa los logs arriba.${N}"
        exit 1
    fi
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        echo -e "${G}[dashboard] ✅ Listo en http://localhost:8001${N}"
        break
    fi
    sleep 1
done

cd "$SCRIPT_DIR"

# ─── Opcional: arrancar PHANTOM también desde la terminal ─
if $WITH_PHANTOM && [ -f "ghost_hunter_phantom/master.py" ]; then
    echo ""
    echo -e "${C}[phantom] --with-phantom activo, arrancando Master + Node...${N}"
    curl -s -X POST "http://localhost:8001/api/services/start?name=ghost-phantom-master" >/dev/null
    sleep 2
    curl -s -X POST "http://localhost:8001/api/services/start?name=ghost-phantom-node" >/dev/null
    echo -e "${G}[phantom] ✅ Lanzado vía Control Tower (mismo mecanismo que el botón Start)${N}"
fi

# ─── Resumen ──────────────────────────────────────────────
echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  Sistema activo                                           ║${N}"
echo -e "${C}╠══════════════════════════════════════════════════════════╣${N}"
echo -e "${G}║  ✅ Dashboard:   http://localhost:8001                    ║${N}"
echo -e "${C}║     → Abre 'Control Tower' en el sidebar para:            ║${N}"
echo -e "${C}║        - Iniciar GHOST PHANTOM (Master :8002 + Node)      ║${N}"
echo -e "${C}║        - Ver estado de COMMANDER (/api/commander/*)       ║${N}"
echo -e "${C}║        - Start/Stop/Restart de cualquier módulo           ║${N}"
echo -e "${C}║                                                            ║${N}"
echo -e "${C}║  Tip: bash iniciar_todo.sh --with-phantom                 ║${N}"
echo -e "${C}║       arranca PHANTOM automáticamente sin usar la UI      ║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""
echo -e "${Y}Presiona Ctrl+C para detener todo.${N}"
echo ""

cleanup() {
    echo ""
    echo -e "${R}[shutdown] Apagando todo...${N}"
    kill $RT_PID 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    echo -e "${G}[shutdown] ✅ Apagado completo. 🌹${N}"
    exit 0
}
trap cleanup SIGTERM SIGINT

wait $RT_PID
