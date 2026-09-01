#!/data/data/com.termux/files/usr/bin/bash
# Compatibilidad: el setup anterior podía hacer reset --hard y no preparaba
# Commander. El flujo soportado ahora sincroniza ambos repositorios de forma
# segura y arranca Dashboard + Commander in-process + PHANTOM.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$ROOT/termux_recover.sh" ]; then
    echo "[termux][ERROR] No encuentro termux_recover.sh en $ROOT" >&2
    exit 1
fi

echo "[termux] termux_setup.sh es compatible; usando el recuperador seguro."
echo "[termux] Si ya tienes cambios locales, se detendrá sin borrarlos."
exec bash "$ROOT/termux_recover.sh" "$@"