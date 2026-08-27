#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOURCESEAL — Arranque unificado v2 (Control Tower + Telegram + PDF + Monitor)
# Un solo comando. Un solo puerto (:8001). Todo integrado.
#   :8001 Red-team-tauri Dashboard
#     ├── COMMANDER (in-process /api/commander/*)
#     ├── GHOST PHANTOM (Control Tower Start/Stop)
#     ├── Telegram alerts (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)
#     ├── PDF reports (reportlab)
#     └── Monitoreo continuo (/api/monitor/start)
# =====================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WITH_PHANTOM=false
WITH_MONITOR=false
[ "$1" = "--with-phantom" ] && WITH_PHANTOM=true
[ "$1" = "--full" ] && { WITH_PHANTOM=true; WITH_MONITOR=true; }

R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' P='\033[0;35m' N='\033[0m'

echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  🌹 SOURCESEAL v2 — Arranque unificado completo            ║${N}"
echo -e "${C}║  Dashboard + COMMANDER + PHANTOM + Telegram + PDF + Monitor║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""

cd "$SCRIPT_DIR"

# ─── 1. Cleanup previo ─────────────────────────────────────
echo -e "${Y}[1/7] Cleanup procesos previos...${N}"
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
sleep 1

# ─── 2. Dependencias Python ─────────────────────────────────
echo -e "${Y}[2/7] Verificando dependencias Python...${N}"
for pkg in fastapi uvicorn httpx; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        echo -e "  ${Y}Instalando $pkg...${N}"
        pip install "$pkg" 2>&1 | tail -1
    fi
done
# reportlab para PDFs
if ! python3 -c "import reportlab" 2>/dev/null; then
    echo -e "  ${Y}Instalando reportlab (para reportes PDF)...${N}"
    pip install reportlab 2>&1 | tail -1
fi
echo -e "  ${G}OK${N}"

# ─── 3. Telegram config ─────────────────────────────────────
echo -e "${Y}[3/7] Configurando Telegram...${N}"
# Cargar desde bashrc si existe
if [ -z "$TELEGRAM_BOT_TOKEN" ] && grep -q "TELEGRAM_BOT_TOKEN" ~/.bashrc 2>/dev/null; then
    export TELEGRAM_BOT_TOKEN="$(grep 'TELEGRAM_BOT_TOKEN' ~/.bashrc | tail -1 | sed "s/.*=//; s/[\"']//g")"
fi
if [ -z "$TELEGRAM_CHAT_ID" ] && grep -q "TELEGRAM_CHAT_ID" ~/.bashrc 2>/dev/null; then
    export TELEGRAM_CHAT_ID="$(grep 'TELEGRAM_CHAT_ID' ~/.bashrc | tail -1 | sed "s/.*=//; s/[\"']//g")"
fi
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    echo -e "  ${G}Telegram configurado: chat_id=$TELEGRAM_CHAT_ID${N}"
else
    echo -e "  ${Y}Telegram no configurado. Para activar:${N}"
    echo -e "  ${Y}  echo 'export TELEGRAM_BOT_TOKEN=\"tu_token\"' >> ~/.bashrc${N}"
    echo -e "  ${Y}  echo 'export TELEGRAM_CHAT_ID=\"tu_chat_id\"' >> ~/.bashrc${N}"
    echo -e "  ${Y}  source ~/.bashrc${N}"
fi

# ─── 4. COMMANDER (repo hermano) ───────────────────────────
echo -e "${Y}[4/7] Detectando COMMANDER...${N}"
if [ -f "../commander/commander.py" ]; then
    export COMMANDER_DIR="$(cd "$SCRIPT_DIR/../commander" && pwd)"
    echo -e "  ${G}Encontrado: $COMMANDER_DIR${N}"
else
    echo -e "  ${Y}No encontrado (carpeta hermana 'commander/')${N}"
    echo -e "  ${Y}/api/commander/* quedara desactivado${N}"
fi

# ─── 5. Build frontend (no-fatal) ───────────────────────────
echo -e "${Y}[5/7] Build frontend...${N}"
if [ -d "tauri-frontend" ]; then
    cd tauri-frontend
    if [ ! -d "node_modules" ]; then
        echo -e "  ${Y}npm install...${N}"
        npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -2 || true
    fi
    echo -e "  ${Y}npm run build...${N}"
    npm run build 2>&1 | tail -3 || echo -e "  ${Y}Build fallo — usando dist/ existente${N}"
    cd "$SCRIPT_DIR"
fi
if [ -d "tauri-frontend/dist" ] && [ -d "redteam/scripts" ]; then
    mkdir -p redteam/scripts/dist
    cp -r tauri-frontend/dist/. redteam/scripts/dist/ 2>/dev/null || true
fi
echo -e "  ${G}OK${N}"

# ─── 6. Arrancar Dashboard (:8001) ─────────────────────────
echo -e "${Y}[6/7] Arrancando Dashboard en :8001...${N}"
cd "$SCRIPT_DIR/redteam/scripts"
PORT=8001 HOST=0.0.0.0 PYTHONUNBUFFERED=1 python3 dashboard_server.py &
RT_PID=$!
echo -e "  ${G}PID: $RT_PID${N}"

for i in $(seq 1 25); do
    if ! kill -0 $RT_PID 2>/dev/null; then
        echo -e "${R}  El proceso murio. Revisa los logs arriba.${N}"
        exit 1
    fi
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        echo -e "  ${G}Dashboard listo en http://localhost:8001${N}"
        break
    fi
    sleep 1
done

cd "$SCRIPT_DIR"

# ─── 7. Servicios opcionales ───────────────────────────────
echo -e "${Y}[7/7] Servicios opcionales...${N}"

# PHANTOM via Control Tower API
if $WITH_PHANTOM && [ -f "ghost_hunter_phantom/master.py" ]; then
    echo -e "  ${P}Arrancando PHANTOM Master + Node...${N}"
    curl -s -X POST "http://localhost:8001/api/services/start?name=ghost-phantom-master" >/dev/null 2>&1
    sleep 2
    curl -s -X POST "http://localhost:8001/api/services/start?name=ghost-phantom-node" >/dev/null 2>&1
    echo -e "  ${G}PHANTOM iniciado via Control Tower${N}"
fi

# NEXUS OMNI v9 via Control Tower API
if $WITH_MONITOR && [ -f "nexus_omni_v9.py" ]; then
    echo -e "  ${P}Arrancando NEXUS OMNI v9 en :8002...${N}"
    curl -s -X POST "http://localhost:8001/api/services/start?name=nexus-omni" >/dev/null 2>&1
    sleep 2
    NX=$(curl -s "http://localhost:8002/" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    if [ "$NX" = "200" ]; then
        echo -e "  ${G}NEXUS OMNI listo en http://localhost:8002${N}"
    else
        echo -e "  ${Y}NEXUS OMNI: esperando inicio (pip install aiohttp si falla)${N}"
    fi
fi

# Telegram test
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    TG=$(curl -s -X POST "http://localhost:8001/api/telegram/test" 2>/dev/null)
    if echo "$TG" | grep -q "true"; then
        echo -e "  ${G}Telegram conectado — mensaje de prueba enviado${N}"
    else
        echo -e "  ${Y}Telegram: token presente pero fallo el test${N}"
    fi
fi

# Monitoreo continuo
if $WITH_MONITOR; then
    echo -e "  ${C}Activando monitoreo continuo (cada 5 min)...${N}"
    curl -s -X POST "http://localhost:8001/api/monitor/start?interval_minutes=5" >/dev/null 2>&1
    echo -e "  ${G}Monitoreo activo — alertas via Telegram + WebSocket${N}"
fi

# ─── Resumen final ─────────────────────────────────────────
echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  🌹 SOURCESEAL — Sistema activo                            ║${N}"
echo -e "${C}╠══════════════════════════════════════════════════════════╣${N}"
echo -e "${G}║  ✅ Dashboard:   http://localhost:8001                     ║${N}"
echo -e "${C}║                                                            ║${N}"
echo -e "${C}║  Sidebar:                                                  ║${N}"
echo -e "${C}║    📍 Mapa de Red    → descubrimiento ARP + TCP (sin root) ║${N}"
echo -e "${C}║    📡 COMMANDER      → escaneo nmap + OSINT                 ║${N}"
echo -e "${C}║    🏢 Control Tower  → PHANTOM Start/Stop                  ║${N}"
echo -e "${C}║    🗺️ Topología      → grafo de red interactivo            ║${N}"
echo -e "${C}║    📷 Cámaras       → IoT auto-access                     ║${N}"
echo -e "${C}║                                                            ║${N}"
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
echo -e "${G}║  📡 Telegram:      CONECTADO (chat: $TELEGRAM_CHAT_ID)           ║${N}"
else
echo -e "${Y}║  📡 Telegram:      NO CONFIGURADO                           ║${N}"
fi
echo -e "${C}║  📄 PDF:           /api/report/pdf (pip install reportlab) ║${N}"
echo -e "${C}║  🔄 Monitor:        /api/monitor/start?interval_minutes=5   ║${N}"
echo -e "${C}║                                                            ║${N}"
echo -e "${C}║  Comandos rapidos:                                          ║${N}"
echo -e "${C}║    bash iniciar_todo.sh          → solo dashboard           ║${N}"
echo -e "${C}║    bash iniciar_todo.sh --with-phantom → + PHANTOM         ║${N}"
echo -e "${C}║    bash iniciar_todo.sh --full          → + PHANTOM + Monitor║${N}"
echo -e "${C}║                                                            ║${N}"
echo -e "${C}║  Ctrl+C detiene todo.                                       ║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""

cleanup() {
    echo ""
    echo -e "${R}[shutdown] Apagando todo...${N}"
    kill $RT_PID 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom" 2>/dev/null || true
    echo -e "${G}[shutdown] Apagado completo. Hasta pronto.${N}"
    exit 0
}
trap cleanup SIGTERM SIGINT

wait $RT_PID
