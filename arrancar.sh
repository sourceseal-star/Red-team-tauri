#!/data/data/com.termux/files/usr/bin/bash
# Compatibilidad con el launcher histórico.
#
# La versión anterior hacía git stash/pull durante el arranque y podía
# detenerse con "cannot pull with rebase: You have unstaged changes".
# El flujo seguro y unificado está en termux_recover.sh.
#
#   bash arrancar.sh          → sincroniza, prepara y arranca todo
#   bash arrancar_termux.sh   → arranca lo local sin sincronizar

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$ROOT/termux_recover.sh" ]; then
    echo "[arranque][ERROR] No encuentro termux_recover.sh en $ROOT" >&2
    exit 1
fi

# ─── SOL AUTÓNOMA ──────────────────────────────────────────────────────
# Arrancar Sol autónoma si no está corriendo (antes del exec al launcher)
if [ -f "$HOME/.sol/sol.pid" ]; then
    SOL_PID=$(cat "$HOME/.sol/sol.pid" 2>/dev/null)
    if [ -n "$SOL_PID" ] && ! kill -0 "$SOL_PID" 2>/dev/null; then
        rm -f "$HOME/.sol/sol.pid"
        bash "$ROOT/sol.sh" start 2>/dev/null || true
    fi
else
    bash "$ROOT/sol.sh" start 2>/dev/null || true
fi

echo "[arranque] Usando el launcher unificado seguro."
echo "[arranque] Los cambios locales no se borrarán."
exec bash "$ROOT/termux_recover.sh" "$@"
