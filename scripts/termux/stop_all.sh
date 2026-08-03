#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# SourceSeal Console Pro — Stop All Services
# ============================================

PROJECT_DIR="$HOME/Red-team-tauri"
PID_DIR="$PROJECT_DIR/.pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "${CYAN}🛑 Deteniendo servicios SourceSeal...${NC}"

# Detener por PID files
if [ -d "$PID_DIR" ]; then
    for pidfile in "$PID_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
                echo "${GREEN}   ✅ $name detenido (PID: $pid)${NC}"
            fi
            rm -f "$pidfile"
        fi
    done
fi

# Matar procesos huérfanos
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "canary_monitor.py" 2>/dev/null || true

echo "${GREEN}✅ Todos los servicios detenidos${NC}"
