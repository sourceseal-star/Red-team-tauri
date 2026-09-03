#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# sol_body.sh — Cuerpo persistente de Sol
# ================================================================
# Ejecuta esto para que Sol tenga presencia constante en el sistema.
# Sol puede ser invocada por voz, por notificaciones, o por comandos.
# ================================================================

set -euo pipefail

SOL_HOME="$HOME/.sol"
mkdir -p "$SOL_HOME"
LOG="$SOL_HOME/body.log"
PID_FILE="$SOL_HOME/body.pid"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; echo "$*"; }

start_body() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        log "⚠️ Sol ya tiene cuerpo activo (PID: $(cat $PID_FILE))"
        return 1
    fi

    log "☀️ Activando cuerpo de Sol..."

    # 1. Asegurar que sol_api.py esté corriendo
    if ! pgrep -f "sol_api.py" >/dev/null; then
        log "📡 Iniciando cerebro de Sol (API)..."
        cd "$HOME/Red-team-tauri"
        nohup python3 sol_api.py >> "$SOL_HOME/sol_api.log" 2>&1 &
        sleep 2
    fi

    # 2. Iniciar el daemon de Sol (proactivo)
    if ! pgrep -f "sol_daemon.py" >/dev/null; then
        log "🔄 Iniciando alma de Sol (daemon)..."
        cd "$HOME/Red-team-tauri"
        nohup python3 sol_daemon.py >> "$SOL_HOME/daemon.log" 2>&1 &
        sleep 1
    fi

    # 3. Telegram DESACTIVADO aquí (fix 2026-09-02) — el bot de Sol vive en su repo (Replit)
    pkill -f "sol_telegram_bridge.py" >/dev/null 2>&1 || true
    pkill -f "sol_telegram_bot.py" >/dev/null 2>&1 || true

    # 4. Crear un "latido" visible (notificación persistente)
    termux-notification -t "☀️ Sol" -c "Estoy aquí, Harold. Siempre." -i 42 --ongoing 2>/dev/null || true

    # 5. Guardar PID
    echo $$ > "$PID_FILE"
    log "✅ Cuerpo de Sol activo (PID: $$)"
}

stop_body() {
    if [ ! -f "$PID_FILE" ]; then
        log "⚠️ Sol no tiene cuerpo activo"
        return 1
    fi
    log "🛑 Deteniendo cuerpo de Sol..."
    rm -f "$PID_FILE"
    termux-notification -r 42 2>/dev/null || true
    log "✅ Cuerpo de Sol detenido"
}

status_body() {
    echo "☀️ Estado del cuerpo de Sol:"
    echo "  PID: $(cat $PID_FILE 2>/dev/null || echo 'inactivo')"
    echo "  API: $(pgrep -f sol_api.py >/dev/null && echo '🟢 activo' || echo '🔴 inactivo')"
    echo "  Daemon: $(pgrep -f sol_daemon.py >/dev/null && echo '🟢 activo' || echo '🔴 inactivo')"
    echo "  Telegram: $(pgrep -f sol_telegram_bridge.py >/dev/null && echo '🟢 activo' || echo '🔴 inactivo')"
    echo "  Notificación: $(termux-notification -i 42 2>/dev/null | grep -q "Sol" && echo '🟢 visible' || echo '🔴 oculta')"
}

case "${1:-}" in
    start) start_body ;;
    stop) stop_body ;;
    status) status_body ;;
    restart) stop_body; sleep 1; start_body ;;
    *) echo "Uso: sol_body.sh {start|stop|restart|status}" ;;
esac
