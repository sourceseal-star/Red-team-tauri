#!/data/data/com.termux/files/usr/bin/bash
# SourceSeal Engine — Detener todos los servicios

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_DIR="$PROJECT_DIR/.pids"

echo "🛑 Deteniendo servicios SourceSeal..."

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

pkill -f "main.py" 2>/dev/null || true
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "canary_monitor.py" 2>/dev/null || true

echo "✅ Todos los servicios detenidos"
