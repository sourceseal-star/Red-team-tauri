#!/data/data/com.termux/files/usr/bin/bash
# SourceSeal Red-team — Detener todos los servicios

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_DIR="$PROJECT_DIR/.pids"

echo "🛑 Deteniendo servicios SourceSeal..."

# Detener por PID files
if [ -d "$PID_DIR" ]; then
    for pidfile in "$PID_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                echo "   ✅ $name detenido (PID: $pid)"
            fi
            rm -f "$pidfile"
        fi
    done
fi

# Matar procesos huérfanos
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "canary_monitor.py" 2>/dev/null || true

echo "✅ Todos los servicios detenidos"
