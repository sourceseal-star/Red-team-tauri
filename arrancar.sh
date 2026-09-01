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

echo "[arranque] Usando el launcher unificado seguro."
echo "[arranque] Los cambios locales no se borrarán."
exec bash "$ROOT/termux_recover.sh" "$@"