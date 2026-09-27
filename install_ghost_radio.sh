#!/usr/bin/env bash
# Instalador local, idempotente y sin instalación automática de drivers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${GHOST_RADIO_PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/share/ghost-radio"
CONFIG_DIR="${GHOST_RADIO_CONFIG_DIR:-$HOME/.config/ghost-radio}"

for command in bash python3; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "[ghost-radio] falta el comando requerido: $command" >&2
        exit 1
    }
done

test -f "$ROOT/ghost_radio_v3.py"
test -f "$ROOT/boot_ghost.sh"

mkdir -p "$BIN_DIR" "$LIB_DIR" "$CONFIG_DIR"
install -m 0755 "$ROOT/ghost_radio_v3.py" "$BIN_DIR/ghost-radio"
install -m 0755 "$ROOT/boot_ghost.sh" "$BIN_DIR/boot-ghost"
install -m 0644 "$ROOT/redteam/scripts/channel_doctor.py" "$LIB_DIR/channel_doctor.py"

CONFIG_FILE="$CONFIG_DIR/config.json"
if [ ! -e "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<'EOF'
{
  "backend": "http://127.0.0.1:8001",
  "transmission_enabled": false,
  "note": "Ghost Radio v3 no transmite; requiere un driver/TNC verificado para cambiar ese estado."
}
EOF
fi

echo "[ghost-radio] instalado en $BIN_DIR"
echo "[ghost-radio] configuración: $CONFIG_FILE"
echo "[ghost-radio] prueba segura: $BIN_DIR/boot-ghost doctor --json"
echo "[ghost-radio] no se instalaron drivers ni se activó hardware."