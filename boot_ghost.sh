#!/usr/bin/env bash
# Arranque seguro del conjunto Ghost: diagnóstico por defecto.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADIO="$ROOT/ghost_radio_v3.py"
if [ ! -f "$RADIO" ] && [ -x "$ROOT/ghost-radio" ]; then
    RADIO="$ROOT/ghost-radio"
fi
if [ ! -f "$RADIO" ]; then
    echo "[ghost-radio] no se encuentra ghost_radio_v3.py ni ghost-radio junto al wrapper" >&2
    exit 1
fi

usage() {
    cat <<'EOF'
Uso:
  boot_ghost.sh doctor
  boot_ghost.sh scan --target HOST --confirm-scope [--json]
  boot_ghost.sh phantom [master|node|all]

doctor es el modo predeterminado y no activa hardware ni transmite.
EOF
}

case "${1:-doctor}" in
    doctor)
        shift || true
        exec python3 "$RADIO" doctor "$@"
        ;;
    scan)
        shift
        exec python3 "$RADIO" scan "$@"
        ;;
    phantom)
        shift
        exec bash "$ROOT/ghost_hunter_phantom/start.sh" "${1:-all}"
        ;;
    -h|--help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac