#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
# SOL START — Arranque unificado de todo el ecosistema SourceSeal
# Levanta: Backend TACTICAL (:8001) + GHOST PHANTOM (:8002) + SOL Bridge
# Uso:  bash sol_start.sh          (arranque completo)
#       bash sol_start.sh --bridge  (solo SOL Bridge)
#       bash sol_start.sh --check   (verificar dependencias)
# ════════════════════════════════════════════════════════════════════
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; W='\033[1;37m'; N='\033[0m'

banner() {
    echo ""
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo -e "${W}  🌅 SOL — SourceSeal Unified Start v1.0${N}"
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo ""
}

# ════════════════════════════════════════════════════════════════════
# CARGAR .env (seguro — sin recursión)
# ════════════════════════════════════════════════════════════════════
load_env() {
    if [ -f "$ROOT/.env" ]; then
        # Filtrar líneas que no son variables (comandos pegados por error)
        grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ROOT/.env" | while IFS= read -r line; do
            export "$line" 2>/dev/null || true
        done
        echo -e "${G}✅ .env cargado${N}"
    else
        echo -e "${Y}⚠️  .env no encontrado. Copia .env.example a .env${N}"
    fi
}

# ════════════════════════════════════════════════════════════════════
# VERIFICAR DEPENDENCIAS
# ════════════════════════════════════════════════════════════════════
check_deps() {
    banner
    echo -e "${W}🔍 Verificando dependencias...${N}"
    echo ""
    
    local OK=0; local FAIL=0
    
    for cmd in python3 curl git; do
        if command -v "$cmd" >/dev/null 2>&1; then
            echo -e "  ${G}✅${N} $cmd"
            OK=$((OK+1))
        else
            echo -e "  ${R}❌${N} $cmd (instala: pkg install $cmd)"
            FAIL=$((FAIL+1))
        fi
    done
    
    # Python deps
    python3 -c "import fastapi" 2>/dev/null && echo -e "  ${G}✅${N} fastapi" || echo -e "  ${R}❌${N} fastapi (pip install fastapi uvicorn)"
    python3 -c "from cryptography.fernet import Fernet" 2>/dev/null && echo -e "  ${G}✅${N} cryptography" || echo -e "  ${Y}⚠️${N} cryptography"
    
    # Telegram token
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        echo -e "  ${G}✅${N} TELEGRAM_BOT_TOKEN configurado"
    else
        echo -e "  ${R}❌${N} TELEGRAM_BOT_TOKEN no configurado en .env"
    fi
    
    if [ -n "$TELEGRAM_CHAT_ID" ]; then
        echo -e "  ${G}✅${N} TELEGRAM_CHAT_ID configurado"
    else
        echo -e "  ${Y}⚠️${N} TELEGRAM_CHAT_ID no configurado (bot responderá a cualquiera)"
    fi
    
    echo ""
    echo -e "${W}Resultado: ${G}$OK OK${W} · ${R}$FAIL FAIL${N}"
    
    # Verificar token de Telegram
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        echo ""
        echo -e "${C}Verificando token de Telegram...${N}"
        RESPONSE=$(curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" 2>/dev/null)
        if echo "$RESPONSE" | grep -q '"ok":true'; then
            BOT_NAME=$(echo "$RESPONSE" | python3 -c "import sys,json; print('@'+json.load(sys.stdin)['result']['username'])" 2>/dev/null)
            echo -e "  ${G}✅${N} Bot conectado: $BOT_NAME"
        else
            echo -e "  ${R}❌${N} Token inválido o sin conexión"
        fi
    fi
}

# ════════════════════════════════════════════════════════════════════
# MATAR PROCESOS ZOMBIE
# ════════════════════════════════════════════════════════════════════
kill_zombies() {
    echo -e "${Y}🧹 Limpiando procesos zombie...${N}"
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "sol_telegram_bridge.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    if command -v fuser >/dev/null 2>&1; then
        fuser -k 8001/tcp 2>/dev/null || true
        fuser -k 8002/tcp 2>/dev/null || true
    fi
    sleep 2
    echo -e "${G}✅ Puertos liberados${N}"
}

# ════════════════════════════════════════════════════════════════════
# LEVANTAR BACKEND TACTICAL (:8001)
# ════════════════════════════════════════════════════════════════════
start_backend() {
    echo -e "${C}📡 Levantando Backend TACTICAL en :8001...${N}"
    cd "$ROOT/redteam/scripts"
    export PORT=8001 HOST=0.0.0.0 PYTHONUNBUFFERED=1
    
    python3 dashboard_server.py > "$ROOT/logs/tactical.log" 2>&1 &
    BACKEND_PID=$!
    echo -e "  ${G}✅${N} Backend PID: $BACKEND_PID"
    
    # Esperar a que arranque
    READY=0
    for i in $(seq 1 20); do
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo -e "  ${R}❌ Backend murió. Revisa logs/tactical.log${N}"
            tail -5 "$ROOT/logs/tactical.log" 2>/dev/null
            return 1
        fi
        HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/health" 2>/dev/null || echo "000")
        if [ "$HTTP" = "200" ]; then
            echo -e "  ${G}✅${N} Backend listo (health=200)"
            READY=1
            break
        fi
        sleep 1
    done
    
    if [ "$READY" != "1" ]; then
        echo -e "  ${Y}⚠️${N} Backend no respondió en 20s (puede estar arrancando)"
    fi
    cd "$ROOT"
}

# ════════════════════════════════════════════════════════════════════
# LEVANTAR GHOST PHANTOM (:8002)
# ════════════════════════════════════════════════════════════════════
start_ghost() {
    if [ ! -d "$ROOT/ghost_hunter_phantom" ]; then
        echo -e "${Y}⚠️${N} ghost_hunter_phantom/ no encontrado — saltando"
        return
    fi
    echo -e "${C}👻 Levantando GHOST PHANTOM en :8002...${N}"
    cd "$ROOT/ghost_hunter_phantom"
    BACKEND_API="http://localhost:8001" MASTER_PORT=8002 NUM_NODES=1 bash start.sh all > "$ROOT/logs/ghost.log" 2>&1 &
    GHOST_PID=$!
    echo -e "  ${G}✅${N} GHOST PID: $GHOST_PID"
    cd "$ROOT"
}

# ════════════════════════════════════════════════════════════════════
# LEVANTAR SOL TELEGRAM BRIDGE
# ════════════════════════════════════════════════════════════════════
start_sol() {
    if [ ! -f "$ROOT/sol_telegram_bridge.py" ]; then
        echo -e "${R}❌ sol_telegram_bridge.py no encontrado${N}"
        return 1
    fi
    echo -e "${C}🌅 Levantando SOL Telegram Bridge...${N}"
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        echo -e "${R}❌ TELEGRAM_BOT_TOKEN no configurado. No se puede iniciar SOL.${N}"
        echo -e "   Agrega a .env: TELEGRAM_BOT_TOKEN=tu_token"
        return 1
    fi
    
    python3 "$ROOT/sol_telegram_bridge.py" > "$ROOT/logs/sol.log" 2>&1 &
    SOL_PID=$!
    echo -e "  ${G}✅${N} SOL PID: $SOL_PID"
    
    sleep 3
    if kill -0 "$SOL_PID" 2>/dev/null; then
        echo -e "  ${G}✅${N} SOL Bridge activo"
        # Verificar que el log no tenga errores
        if grep -q "ERROR\|Traceback\|FATAL" "$ROOT/logs/sol.log" 2>/dev/null; then
            echo -e "  ${Y}⚠️${N} Posible error en log:"
            tail -5 "$ROOT/logs/sol.log"
        fi
    else
        echo -e "  ${R}❌ SOL murió. Revisa logs/sol.log${N}"
        tail -10 "$ROOT/logs/sol.log" 2>/dev/null
    fi
}

# ════════════════════════════════════════════════════════════════════
# RESUMEN
# ════════════════════════════════════════════════════════════════════
show_summary() {
    echo ""
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo -e "${W}  🌅 SOL — Sistema activo${N}"
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo ""
    echo -e "  ${G}📡 Backend TACTICAL${N}  → http://localhost:8001"
    echo -e "     Health: http://localhost:8001/api/health"
    echo -e "     Dashboard: http://localhost:8001/"
    echo ""
    echo -e "  ${G}👻 GHOST PHANTOM${N}    → http://localhost:8002"
    echo -e "     Status: http://localhost:8002/api/status"
    echo ""
    echo -e "  ${G}🌅 SOL Bridge${N}       → Telegram Bot activo"
    echo -e "     Logs: $ROOT/logs/sol.log"
    echo ""
    echo -e "  ${W}Comandos de Telegram:${N}"
    echo -e "    /status   — Estado del sistema"
    echo -e "    /health   — Health del backend"
    echo -e "    /alerts   — Alertas recientes"
    echo -e "    /scan IP  — Escaneo rápido"
    echo -e "    /phantom  — Estado GHOST"
    echo -e "    /audits   — Auditorías"
    echo -e "    /help     — Ayuda completa"
    echo ""
    echo -e "  ${Y}Logs:${N} $ROOT/logs/"
    echo -e "  ${Y}Detener:${N} pkill -f dashboard_server; pkill -f sol_telegram; pkill -f ghost_hunter"
    echo ""
}

# ════════════════════════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════════════════════════
cleanup() {
    echo ""
    echo -e "${Y}🛑 Apagando sistema SOL...${N}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $GHOST_PID 2>/dev/null || true
    kill $SOL_PID 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "sol_telegram_bridge.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    echo -e "${G}✅ Sistema apagado${N}"
    exit 0
}

# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════
mkdir -p "$ROOT/logs"

trap cleanup SIGTERM SIGINT

case "${1:-}" in
    --check)
        load_env
        check_deps
        ;;
    --bridge)
        load_env
        banner
        start_sol
        ;;
    --backend)
        load_env
        banner
        kill_zombies
        start_backend
        show_summary
        wait
        ;;
    --help|-h)
        echo "SOL Start — Arranque unificado SourceSeal"
        echo ""
        echo "Uso:"
        echo "  bash sol_start.sh              # Arranque completo (Backend + GHOST + SOL)"
        echo "  bash sol_start.sh --check       # Verificar dependencias y token"
        echo "  bash sol_start.sh --bridge      # Solo SOL Telegram Bridge"
        echo "  bash sol_start.sh --backend      # Solo Backend TACTICAL"
        echo "  bash sol_start.sh --help         # Esta ayuda"
        ;;
    *)
        load_env
        banner
        kill_zombies
        start_backend
        start_ghost
        start_sol
        show_summary
        # Mantener vivo
        echo -e "${C}Presiona Ctrl+C para detener todo...${N}"
        wait
        ;;
esac
