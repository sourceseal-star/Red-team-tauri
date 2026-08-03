#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# SourceSeal Console Pro — Start All Services
# Termux Edition v2.1
# ============================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

PROJECT_DIR="$HOME/Red-team-tauri"
REDTEAM_DIR="$PROJECT_DIR/redteam"
REDTEAM_DIR="$PROJECT_DIR/redteam"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/.pids"

# Crear directorios necesarios
mkdir -p "$LOG_DIR" "$PID_DIR" "$PROJECT_DIR/evidence/canary"

echo "${BOLD}${RED}"
echo "  ███████╗ ██████╗ ██╗   ██╗██████╗  ██████╗ ███████╗███████╗ █████╗ ██╗     "
echo "  ██╔════╝██╔═══██╗██║   ██║██╔══██╗██╔════╝ ██╔════╝██╔════╝██╔══██╗██║     "
echo "  ███████╗██║   ██║██║   ██║██████╔╝██║  ███╗█████╗  ███████╗███████║██║     "
echo "  ╚════██║██║   ██║██║   ██║██╔══██╗██║   ██║██╔══╝  ╚════██║██╔══██║██║     "
echo "  ███████║╚██████╔╝╚██████╔╝██║  ██║╚██████╔╝███████╗███████║██║  ██║███████╗"
echo "  ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝"
echo "${NC}"
echo "${CYAN}  Console Pro v2.1.0 | Infraestructura Real | Termux Edition${NC}"
echo ""

# Función para verificar si un puerto está libre
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        return 1
    fi
    return 0
}

# Función para matar proceso en puerto
kill_port() {
    local port=$1
    local pid=$(netstat -tulnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1)
    if [ -n "$pid" ]; then
        kill -9 "$pid" 2>/dev/null || true
    fi
}

# ============================================
# 1. INICIAR BACKEND PRINCIPAL (puerto 8001)
# ============================================
echo "${CYAN}[1/4] Iniciando Backend Engine...${NC}"
if check_port 8001; then
    cd "$REDTEAM_DIR"
    PORT=8001 PYTHONUNBUFFERED=1 nohup python3 scripts/dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
    sleep 3
    if check_port 8001; then
        echo "${GREEN}   ✅ Backend corriendo en http://127.0.0.1:8001${NC}"
        echo "${GREEN}   📚 Docs: http://127.0.0.1:8001/docs${NC}"
    else
        echo "${YELLOW}   ⚠️  Backend iniciando (ver logs)...${NC}"
    fi
else
    echo "${YELLOW}   ⚠️  Puerto 8001 ocupado. Reiniciando...${NC}"
    kill_port 8001
    sleep 2
    cd "$REDTEAM_DIR"
    PORT=8001 PYTHONUNBUFFERED=1 nohup python3 scripts/dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
    echo "${GREEN}   ✅ Backend reiniciado${NC}"
fi

# ============================================
# 2. INICIAR CANARY MONITOR (puerto 9999)
# ============================================
echo "${CYAN}[2/4] Iniciando Canary Monitor...${NC}"
if check_port 9999; then
    cd "$REDTEAM_DIR/monitor"
    nohup python canary_monitor.py --watch "$PROJECT_DIR/evidence/canary" > "$LOG_DIR/canary_monitor.log" 2>&1 &
    echo $! > "$PID_DIR/canary_monitor.pid"
    sleep 2
    if check_port 9999; then
        echo "${GREEN}   ✅ Canary Monitor en http://127.0.0.1:9999${NC}"
    else
        echo "${YELLOW}   ⚠️  Monitor iniciando...${NC}"
    fi
else
    echo "${YELLOW}   ⚠️  Puerto 9999 ocupado${NC}"
fi

# ============================================
# 3. INICIAR CANARY DASHBOARD (puerto 8888)
# ============================================
echo "${CYAN}[3/4] Iniciando Canary Dashboard...${NC}"
if check_port 8888; then
    cd "$REDTEAM_DIR/monitor"
    nohup python canary_monitor.py --dashboard --port 8888 > "$LOG_DIR/canary_dashboard.log" 2>&1 &
    echo $! > "$PID_DIR/canary_dashboard.pid"
    sleep 2
    if check_port 8888; then
        echo "${GREEN}   ✅ Dashboard en http://127.0.0.1:8888${NC}"
    else
        echo "${YELLOW}   ⚠️  Dashboard iniciando...${NC}"
    fi
else
    echo "${YELLOW}   ⚠️  Puerto 8888 ocupado${NC}"
fi

# ============================================
# 4. GENERAR CANARY TOKEN (si no existe)
# ============================================
echo "${CYAN}[4/4] Verificando Canary Tokens...${NC}"
if [ ! -d "$PROJECT_DIR/canary_deploy" ]; then
    cd "$REDTEAM_DIR/deception"
    python3 svg_canary.py  # Genera SVG + HTML por defecto
    echo "${GREEN}   ✅ Canary token generado${NC}"
else
    echo "${GREEN}   ✅ Canary token ya existe${NC}"
fi

# ============================================
# RESUMEN
# ============================================
echo ""
echo "${BOLD}${GREEN}{'='*60}${NC}"
echo "${BOLD}${GREEN}  🚀 TODOS LOS SERVICIOS INICIADOS${NC}"
echo "${BOLD}${GREEN}{'='*60}${NC}"
echo ""
echo "${CYAN}  Servicios activos:${NC}"
echo "    ${GREEN}●${NC} Backend API      → http://127.0.0.1:8001"
echo "    ${GREEN}●${NC} API Docs         → http://127.0.0.1:8001/docs"
echo "    ${GREEN}●${NC} Canary Monitor   → http://127.0.0.1:9999"
echo "    ${GREEN}●${NC} Canary Dashboard → http://127.0.0.1:8888"
echo ""
echo "${CYAN}  Infraestructura escaneable:${NC}"
echo "    ${MAGENTA}●${NC} 20 Cámaras IP    → /api/scan/cameras"
echo "    ${MAGENTA}●${NC} 5 Routers        → /api/scan/routers"
echo "    ${MAGENTA}●${NC} 2 Repetidores    → /api/scan/routers"
echo "    ${MAGENTA}●${NC} 1 Antena Radio   → /api/scan/antenna"
echo ""
echo "${CYAN}  Comandos útiles:${NC}"
echo "    ${YELLOW}►${NC} Ver logs backend:     tail -f $LOG_DIR/backend.log"
echo "    ${YELLOW}►${NC} Ver logs canary:      tail -f $LOG_DIR/canary_monitor.log"
echo "    ${YELLOW}►${NC} Detener todo:         bash $PROJECT_DIR/scripts/termux/stop_all.sh"
echo "    ${YELLOW}►${NC} Escanear cámaras:     curl -X POST http://127.0.0.1:8001/api/scan/cameras \"
echo "                              -H 'Content-Type: application/json' \"
echo "                              -d '{\"target_range\":\"192.168.10.0/24\"}'"
echo ""
echo "${CYAN}  Canary Token:${NC}"
echo "    ${YELLOW}►${NC} Archivo SVG: $PROJECT_DIR/canary_deploy/documento_confidencial.svg"
echo "    ${YELLOW}►${NC} Archivo HTML: $PROJECT_DIR/canary_deploy/index.html"
echo "    ${YELLOW}►${NC} Evidencia: $PROJECT_DIR/evidence/canary/"
echo ""
echo "${BOLD}${GREEN}{'='*60}${NC}"
echo ""

# Iniciar Flutter si está disponible
if command -v flutter &> /dev/null; then
    echo "${CYAN}¿Iniciar app Flutter? (s/n)${NC}"
    read -t 5 -n 1 -r START_FLUTTER || START_FLUTTER="n"
    echo ""
    if [[ $START_FLUTTER =~ ^[Ss]$ ]]; then
        cd "$PROJECT_DIR"
        flutter run
    fi
fi
